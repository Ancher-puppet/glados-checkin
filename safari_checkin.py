"""Normal Safari WebDriver on GitHub's macOS runner; no CAPTCHA interactions."""

import json
import os
import sys

from checkin import (BASE, CheckinError, checked_today, classify, credentials,
                     redact, summary, verified_browser)


# Observe the site's own XMLHttpRequest response without changing its request.
# Keep only non-secret diagnostics; never store nonce/proof/CAPTCHA token values.
OBSERVE = """
window.__gladosCheckinObservation = null;
const originalOpen = XMLHttpRequest.prototype.open;
const originalSend = XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.open = function(method, url, ...rest) {
  const target = new URL(url, location.href);
  this.__observeGlados = method.toUpperCase() === 'POST' &&
    target.origin === location.origin && target.pathname === '/api/user/checkin';
  return originalOpen.call(this, method, url, ...rest);
};
XMLHttpRequest.prototype.send = function(body) {
  if (this.__observeGlados) {
    let payload = {};
    try { payload = JSON.parse(body); } catch (_) {}
    const state = payload.tsState;
    const info = {challenge_present: Boolean(payload.nonce),
      turnstile_token_present: Boolean(payload.turnstile),
      verification_state: ['ok','off','error','timeout'].includes(state) ? state : 'unknown'};
    this.addEventListener('load', () => {
      try {
        const data = JSON.parse(this.responseText);
        const safe = {};
        for (const key of ['code','reason','message','repeated','points']) {
          if (['string','number','boolean'].includes(typeof data[key]) || data[key] === null)
            safe[key] = data[key];
        }
        window.__gladosCheckinObservation = {status: this.status, info, data: safe};
      } catch (_) { window.__gladosCheckinObservation = {invalid_json: true}; }
    }, {once: true});
  }
  return originalSend.call(this, body);
};
"""


def run():
    from selenium import webdriver
    from selenium.common.exceptions import TimeoutException
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    cookies, expected_ua = credentials(os.environ)
    verify = os.environ.get("GLADOS_VERIFY_BROWSER") == "1"
    driver = webdriver.Safari()
    driver.set_page_load_timeout(45)
    driver.set_script_timeout(30)

    def points():
        data = driver.execute_async_script("""
          const done = arguments[arguments.length - 1];
          fetch('/api/user/points', {credentials: 'same-origin'})
            .then(response => response.json()).then(done)
            .catch(() => done({request_failed: true}));
        """)
        if not isinstance(data, dict) or data.get("request_failed"):
            raise CheckinError("积分查询失败，无法核对签到状态。")
        if data.get("code") == -2:
            raise CheckinError("登录已失效，需要更新仓库 Cookie。")
        return data

    try:
        driver.get(BASE)
        for cookie in cookies:
            driver.add_cookie({"name": cookie["name"], "value": cookie["value"],
                               "domain": "glados.cloud", "path": "/", "secure": True})
        driver.get(BASE + "/console/checkin")
        actual_ua = driver.execute_script("return navigator.userAgent")
        print("原生 Safari 已启动；与登录 User-Agent 完全一致：" + str(actual_ua == expected_ua), flush=True)
        before = points()
        if checked_today(before) and not verify:
            summary("今日已签到：已核对北京时间积分流水。")
            return
        button = WebDriverWait(driver, 45).until(EC.element_to_be_clickable((By.XPATH,
            "//button[normalize-space(.)='Checkin' or normalize-space(.)='Check in' or normalize-space(.)='签到']")))
        driver.execute_script(OBSERVE)
        button.click()
        observed = WebDriverWait(driver, 150).until(
            lambda browser: browser.execute_script("return window.__gladosCheckinObservation"))
        if observed.get("invalid_json") or observed.get("status") != 200:
            raise CheckinError("签到接口未返回 HTTP 200 的 JSON 响应。")
        info = observed["info"]
        print("网页验证状态：" + json.dumps(info, ensure_ascii=False), flush=True)
        data = observed["data"]
        safe = {key: redact(value, cookies) if isinstance(value, str) else value for key, value in data.items()}
        print("签到响应：" + json.dumps(safe, ensure_ascii=False), flush=True)
        result = classify(data)
        if result == "needs_confirmation":
            if not checked_today(points()):
                raise CheckinError("服务器返回 code=1，但流水未确认今日签到。")
            result = "already_checked"
        if verify and not verified_browser(info):
            raise CheckinError("今日签到状态已核对，但原生 Safari 未完成挑战/验证；不能判定无人值守签到可用。")
        summary("官方网页返回今日已签到；本次未新增奖励。" if result == "already_checked" else "官方网页已确认签到成功。")
    except TimeoutException:
        raise CheckinError("原生 Safari 页面等待超时，可能需要人工验证；未确认自动签到成功。") from None
    finally:
        driver.quit()


if __name__ == "__main__":
    try:
        run()
    except CheckinError as error:
        summary("签到失败：" + str(error))
        sys.exit(1)
    except Exception as error:
        summary("签到失败：运行异常（" + type(error).__name__ + "），未确认签到成功。")
        sys.exit(1)
