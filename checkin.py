"""Use the official check-in page; never fabricate or solve CAPTCHA tokens."""

import json
import os
import re
import sys
from datetime import datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

BASE = "https://glados.cloud"
BEIJING = ZoneInfo("Asia/Shanghai")


class CheckinError(Exception):
    pass


def credentials(env):
    cookie = env.get("GLADOS_COOKIE", "").strip()
    ua = env.get("GLADOS_USER_AGENT", "").strip()
    if cookie.lower().startswith("cookie:"):
        cookie = cookie.split(":", 1)[1].strip()
    if not cookie or "\n" in cookie or "\r" in cookie:
        raise CheckinError("GLADOS_COOKIE 缺失或包含换行，请更新仓库 Secret。")
    if not ua or "\n" in ua or "\r" in ua:
        raise CheckinError("GLADOS_USER_AGENT 缺失或包含换行，请与 Cookie 一起更新。")
    items = []
    for part in cookie.split(";"):
        name, sep, value = part.strip().partition("=")
        if not sep or not name or not value:
            raise CheckinError("Cookie 格式无效，需要完整的 name=value; name=value。")
        items.append({"name": name, "value": value, "url": BASE + "/"})
    return items, ua


def redact(value, cookies):
    text = str(value)
    for secret in sorted((c["value"] for c in cookies), key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return text


def browser_name(ua):
    if "Firefox/" in ua:
        return "firefox"
    if "Safari/" in ua and not any(x in ua for x in ("Chrome/", "Chromium/", "Edg/")):
        return "webkit"
    return "chromium"


def checked_today(data, today=None):
    """Only a dated check-in ledger entry proves today's prior attendance."""
    if not isinstance(data, dict) or type(data.get("code")) is not int or data["code"] != 0:
        return False
    today = today or datetime.now(BEIJING).date()
    history = data.get("history")
    if not isinstance(history, list):
        return False
    for entry in history:
        if not isinstance(entry, dict) or "checkin" not in str(entry.get("business", "")).lower():
            continue
        value = entry.get("time")
        try:
            if isinstance(value, bool) or value is None:
                continue
            if isinstance(value, (int, float)) or str(value).replace(".", "", 1).isdigit():
                timestamp = float(value)
                if timestamp > 100_000_000_000:
                    timestamp /= 1000
                day = datetime.fromtimestamp(timestamp, BEIJING).date()
            else:
                timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    continue
                day = timestamp.astimezone(BEIJING).date()
        except (ValueError, OverflowError, OSError, TypeError):
            continue
        if day == today:
            return True
    return False


def classify(data):
    if not isinstance(data, dict):
        raise CheckinError("签到接口未返回预期的 JSON 对象。")
    code, reason = data.get("code"), data.get("reason")
    if type(code) is int and code == 0:
        return "already_checked" if data.get("repeated") is True else "success"
    if code == -2:
        raise CheckinError("登录已失效：请从同一次浏览器登录同时更新 Cookie 和 User-Agent。")
    if code == 4 and reason == "device-mismatch":
        raise CheckinError("设备不匹配：请从同一次浏览器登录同时更新 Cookie 和 User-Agent。")
    if code == 5 or reason == "turnstile":
        raise CheckinError("Cloudflare 验证未通过。云端浏览器未能自动完成验证，本次未记录签到；需要人工处理或官方支持的自动接口。")
    if code == 4:
        raise CheckinError("网站拒绝了此次自动签到，本次没有确认成功。")
    if type(code) is int and code == 1:
        return "needs_confirmation"
    raise CheckinError("服务器没有确认签到成功，请查看上方脱敏后的业务错误。")


def verification_info(payload):
    payload = payload if isinstance(payload, dict) else {}
    state = payload.get("tsState")
    return {"challenge_present": bool(payload.get("nonce")),
            "turnstile_token_present": bool(payload.get("turnstile")),
            "verification_state": state if state in ("ok", "off", "timeout", "error") else "unknown"}


def verified_browser(info):
    return (info["challenge_present"] and
            (info["verification_state"] == "off" or
             (info["verification_state"] == "ok" and info["turnstile_token_present"])))


def summary(text):
    print(text, flush=True)
    filename = os.environ.get("GITHUB_STEP_SUMMARY")
    if filename:
        with open(filename, "a", encoding="utf-8") as file:
            file.write(text + "\n\n")


def run():
    from playwright.sync_api import sync_playwright, TimeoutError as BrowserTimeout

    cookies, ua = credentials(os.environ)
    verify = os.environ.get("GLADOS_VERIFY_BROWSER") == "1"
    engine = browser_name(ua)
    print("使用官方网页签到，浏览器引擎：" + engine, flush=True)
    # No stealth flags, challenge replay, CAPTCHA solver, or token injection.
    with sync_playwright() as playwright:
        browser = getattr(playwright, engine).launch(headless=False)
        context = browser.new_context(user_agent=ua, locale="zh-CN", timezone_id="Asia/Shanghai")
        context.add_cookies(cookies)
        page = context.new_page()

        def points():
            response = context.request.get(BASE + "/api/user/points", timeout=30000)
            if response.status != 200:
                raise CheckinError(f"积分查询返回 HTTP {response.status}。")
            data = response.json()
            if isinstance(data, dict) and data.get("code") == -2:
                raise CheckinError("登录已失效：请同时更新仓库中的 Cookie 和 User-Agent。")
            return data

        try:
            page.goto(BASE + "/console/checkin", wait_until="domcontentloaded", timeout=45000)
            before = points()
            if checked_today(before) and not verify:
                summary("今日已签到：已核对北京时间今日积分流水，无需重复提交。")
                return
            button = page.get_by_role("button", name=re.compile(r"^(check\s*in|签到)$", re.I))
            button.wait_for(state="visible", timeout=45000)

            def is_checkin(response):
                parsed = urlsplit(response.url)
                return (parsed.scheme == "https" and parsed.netloc == "glados.cloud"
                        and parsed.path == "/api/user/checkin" and response.request.method == "POST")

            with page.expect_response(is_checkin, timeout=150000) as captured:
                button.click(timeout=15000)
            response = captured.value
            # Log presence/state only, never challenge, proof, or CAPTCHA token values.
            info = verification_info(response.request.post_data_json)
            print("网页验证状态：" + json.dumps(info, ensure_ascii=False), flush=True)
            if response.status != 200:
                raise CheckinError(f"签到接口返回 HTTP {response.status}。")
            data = response.json()
            if not isinstance(data, dict):
                raise CheckinError("签到接口未返回预期 JSON 对象。")
            safe = {k: (redact(data[k], cookies) if isinstance(data.get(k), str) else
                        data.get(k) if isinstance(data.get(k), (int, float, bool, type(None))) else "[OMITTED]")
                    for k in ("code", "reason", "message", "repeated", "points")}
            print("签到响应：" + json.dumps(safe, ensure_ascii=False), flush=True)
            result = classify(data)
            if result == "needs_confirmation":
                if not checked_today(points()):
                    raise CheckinError("code=1，但积分流水未确认今日签到，按失败处理。")
                result = "already_checked"
            if verify and not verified_browser(info):
                raise CheckinError("今日签到状态已核对，但云端页面未完成挑战/验证。重复签到响应不能证明每天无人值守签到可用。")
            if result == "already_checked":
                summary("官方网页返回今日已签到；本次未新增签到奖励。")
            else:
                summary("官方网页的签到接口已确认成功。")
        except BrowserTimeout:
            raise CheckinError("网页等待超时：可能需要人工验证、登录已失效或页面发生变化；没有确认签到成功。") from None
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    try:
        run()
    except CheckinError as error:
        summary("签到失败：" + str(error))
        sys.exit(1)
    except Exception as error:
        summary("签到失败：运行异常（" + type(error).__name__ + "），未确认签到成功。")
        sys.exit(1)
