import sys
import time

from builder.auth import TaobaoAuth


def log(msg):
    print(f"[TaobaoLogin] {msg}", file=sys.stderr)


class TaobaoLogin:

    @classmethod
    def qr_login(cls):
        from playwright.sync_api import sync_playwright

        log("正在启动浏览器...")
        log("请在浏览器窗口中使用淘宝 App 扫码登录")

        auth = TaobaoAuth()

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.goto("https://login.taobao.com/")

            deadline = time.time() + 180
            last_count = 0

            while time.time() < deadline:
                time.sleep(2)
                cookies = page.context.cookies()
                auth.update_cookies({c.get("name"): c.get("value") for c in cookies})
                auth.ensure_device_id()

                if auth.is_login:
                    auth.save()
                    browser.close()
                    log(f"登录成功: unb={auth.unb}, nk={auth.nk}")
                    log(f"Cookie 已持久化到: {auth._storage_path}")
                    return auth

                c = len(auth.cookie)
                if c != last_count:
                    log(f"已检测到 {c} 个 cookie，等待扫码登录...")
                    last_count = c

            browser.close()

        log("扫码超时（180s）")
        return auth

    @classmethod
    def auto(cls):
        auth = TaobaoAuth.load()
        if auth.is_login:
            log(f"从文件加载 cookie 成功: unb={auth.unb}")
            return auth

        auth = cls.qr_login()
        if auth.is_login:
            return auth

        auth = cls.interactive()
        if auth.is_login:
            auth.save()
            return auth

        log("未获取到登录态")
        return auth

    @classmethod
    def interactive(cls):
        print("=" * 60, file=sys.stderr)
        print("请在浏览器中登录淘宝 (https://login.taobao.com/)", file=sys.stderr)
        print("登录后打开开发者工具 → Application → Cookies → taobao.com", file=sys.stderr)
        print("复制全部 cookie 字符串并粘贴到下方：", file=sys.stderr)
        print("=" * 60, file=sys.stderr)
        cookie_str = input("cookie > ").strip()
        if not cookie_str:
            return TaobaoAuth()
        auth = TaobaoAuth()
        auth.prepare_auth(cookie_str)
        auth.ensure_device_id()
        return auth