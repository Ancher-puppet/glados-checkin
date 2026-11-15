"""Run an isolated system Chrome and operate the official verification widget."""

import shutil
import socket
import subprocess
import tempfile
import time
from contextlib import contextmanager
from urllib.parse import urlsplit
from urllib.request import urlopen


@contextmanager
def launch_chrome(playwright):
    executable = next((p for name in ("google-chrome", "google-chrome-stable", "chromium")
                       if (p := shutil.which(name))), None)
    if not executable:
        raise RuntimeError("System Chrome is unavailable")
    with tempfile.TemporaryDirectory(prefix="glados-chrome-") as profile:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        endpoint = f"http://127.0.0.1:{port}"
        process = subprocess.Popen([
            executable, f"--user-data-dir={profile}",
            f"--remote-debugging-port={port}", "--remote-debugging-address=127.0.0.1",
            "--no-first-run", "--no-default-browser-check", "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        browser = None
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("System Chrome exited during startup")
                try:
                    with urlopen(endpoint + "/json/version", timeout=1) as response:
                        ready = response.status == 200
                    if ready:
                        break
                except OSError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("System Chrome startup timed out")
            browser = playwright.chromium.connect_over_cdp(endpoint, timeout=30000)
            yield browser
        finally:
            try:
                if browser:
                    browser.close()
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


def verification_checkbox(node):
    if node.get("role", {}).get("value") != "checkbox":
        return False
    label = str(node.get("name", {}).get("value", "")).lower()
    if not any(word in label for word in ("human", "verify", "真人", "验证")):
        return False
    properties = {p["name"]: p.get("value", {}).get("value")
                  for p in node.get("properties", [])}
    return (bool(node.get("backendDOMNodeId")) and
            properties.get("disabled") is not True and
            properties.get("checked") not in (True, "true"))


def activate_checkbox(page):
    """Press Space only on a named checkbox inside Cloudflare's own frame."""
    for frame in page.frames:
        if urlsplit(frame.url).hostname != "challenges.cloudflare.com":
            continue
        client = None
        try:
            params = {}
            try:
                client = page.context.new_cdp_session(frame)
            except Exception:
                client = page.context.new_cdp_session(page)
                frames = [client.send("Page.getFrameTree")["frameTree"]]
                while frames:
                    item = frames.pop()
                    frames.extend(item.get("childFrames", []))
                    if item.get("frame", {}).get("url") == frame.url:
                        params = {"frameId": item["frame"]["id"]}
                        break
                if not params:
                    continue
            for node in client.send("Accessibility.getFullAXTree", params)["nodes"]:
                if verification_checkbox(node):
                    client.send("DOM.focus", {"backendNodeId": node["backendDOMNodeId"]})
                    page.keyboard.press("Space")
                    print("已操作官网的标准验证勾选框，等待验证结果。", flush=True)
                    return True
        except Exception:
            continue
        finally:
            if client:
                try:
                    client.detach()
                except Exception:
                    pass
    return False


def wait_for_verification(page, required, timeout=45):
    if not required:
        return True
    deadline = time.monotonic() + timeout
    activated = False
    while time.monotonic() < deadline:
        if page.evaluate("""() => {
            try { if (window.turnstile?.getResponse()) return true; } catch (_) {}
            return [...document.querySelectorAll('input[name="cf-turnstile-response"]')]
                .some(input => Boolean(input.value));
        }"""):
            return True
        if not activated:
            activated = activate_checkbox(page)
        page.wait_for_timeout(300)
    return False
