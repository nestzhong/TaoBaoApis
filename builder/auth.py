import json
import os
import sys
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from urllib.parse import unquote

from utils.taobao_utils import generate_device_id, trans_cookies


def default_auth_path():
    override = os.getenv("TBAPIS_AUTH_FILE")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.getenv("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return base / "TaobaoApis" / "auth.json"


def cookies_to_str(cookies: dict) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items())


class TaobaoAuth:
    def __init__(self):
        self.cookie = {}
        self.cookie_str = ""
        self.device_id = None
        self._storage_path = default_auth_path()
        self._dirty = False

    def prepare_auth(self, cookie_str: str = ""):
        cookies = trans_cookies(cookie_str)
        if cookies != self.cookie:
            self._dirty = True
        self.cookie = cookies
        self.cookie_str = cookies_to_str(self.cookie)
        unb = self.cookie.get("unb")
        if unb and not self.device_id:
            self.device_id = generate_device_id(unb)
        return self

    def ensure_device_id(self):
        if not self.device_id:
            unb = self.cookie.get("unb", "")
            self.device_id = generate_device_id(unb) if unb else generate_device_id("0")
        return self.device_id

    def update_cookies(self, cookies, *, persist=False):
        if not cookies:
            if persist:
                self.flush()
            return self
        if hasattr(cookies, "get_dict"):
            cookies = cookies.get_dict()
        try:
            items = cookies.items()
        except AttributeError as exc:
            raise TypeError("cookies must be a mapping or CookieJar") from exc
        changed = False
        for key, value in items:
            key = str(key)
            if value in (None, ""):
                if key in self.cookie:
                    del self.cookie[key]
                    changed = True
                continue
            value = str(value)
            if self.cookie.get(key) != value:
                self.cookie[key] = value
                changed = True
        if changed:
            self.cookie_str = cookies_to_str(self.cookie)
            self._dirty = True
            unb = self.cookie.get("unb")
            if unb and not self.device_id:
                self.device_id = generate_device_id(unb)
        if persist:
            self.flush()
        return self

    def absorb_response(self, response, *, session=None, persist=True):
        if response is not None:
            for item in list(getattr(response, "history", None) or []) + [response]:
                for raw in self._set_cookie_headers(item):
                    parsed = SimpleCookie()
                    try:
                        parsed.load(raw)
                    except (CookieError, TypeError, ValueError):
                        continue
                    self.update_cookies({key: morsel.value
                                         for key, morsel in parsed.items()})
                self.update_cookies(getattr(item, "cookies", None))
        if session is not None:
            self.update_cookies(getattr(session, "cookies", None))
        if persist:
            self.flush()
        return self

    @staticmethod
    def _set_cookie_headers(response):
        headers = getattr(response, "headers", None)
        if headers is None:
            return []
        for method_name in ("get_list", "getlist", "get_all"):
            method = getattr(headers, method_name, None)
            if callable(method):
                try:
                    values = method("set-cookie")
                except (KeyError, TypeError):
                    values = None
                if values:
                    return [str(value) for value in values]
        raw_headers = getattr(getattr(response, "raw", None), "headers", None)
        method = getattr(raw_headers, "getlist", None)
        if callable(method):
            values = method("set-cookie")
            if values:
                return [str(value) for value in values]
        value = headers.get("set-cookie")
        return [str(value)] if value else []

    def flush(self):
        if self._dirty:
            self.save()
        return self

    @property
    def unb(self):
        return self.cookie.get("unb")

    @property
    def nk(self):
        raw = self.cookie.get("_nk_") or self.cookie.get("nk")
        return unquote(raw) if raw else None

    @property
    def sign_token(self):
        raw = self.cookie.get("_m_h5_tk", "")
        return raw.split("_")[0]

    @property
    def is_login(self):
        return bool(self.cookie.get("_m_h5_tk")) and bool(self.cookie.get("unb"))

    def save(self, path=None):
        path = Path(path) if path else self._storage_path
        self._storage_path = path.expanduser().resolve()
        path = self._storage_path
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "cookie": self.cookie,
            "device_id": self.device_id,
        }
        temp_path = path.with_suffix(path.suffix + ".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        try:
            os.chmod(temp_path, 0o600)
        except OSError:
            pass
        os.replace(temp_path, path)
        self._dirty = False
        return str(path)

    @classmethod
    def load(cls, path=None):
        path = (Path(path) if path else default_auth_path()).expanduser().resolve()
        auth = cls()
        auth._storage_path = path
        if not path.exists():
            return auth
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        auth.update_cookies(data.get("cookie", {}))
        auth.device_id = data.get("device_id") or auth.ensure_device_id()
        auth._dirty = False
        return auth

    @classmethod
    def from_env(cls):
        auth = cls.load()
        if not auth.is_login:
            cookie_str = os.getenv("TB_COOKIES", "")
            if cookie_str:
                auth.prepare_auth(cookie_str)
        return auth