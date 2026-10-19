"""官方 ChatGPT OAuth：独立本机回调、PKCE、身份验证及令牌轮换。"""
import base64
from dataclasses import dataclass, field
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import secrets
from threading import Event, RLock, Thread
import time
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

from fastapi import HTTPException
import httpx
import jwt

from app.core import private_store

ACCOUNTS_FILE = "chatgpt-accounts.private"
ISSUER = "https://auth.openai.com"
AUTHORIZE_URL = f"{ISSUER}/api/accounts/authorize"
TOKEN_URL = f"{ISSUER}/api/accounts/oauth/token"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
RESOURCE = "https://api.openai.com/v1"
PLAN_SCOPE = "chatgpt.tokens.use.direct"
SCOPES = f"openid profile email offline_access resource.invoke {PLAN_SCOPE}"
_AUTH_LOCK = RLock()


def _document() -> dict:
    return private_store.read_document(ACCOUNTS_FILE)


def _find_account(document: dict, account_id: str | None = None) -> dict:
    selected = account_id or document.get("active_id")
    account = next((row for row in document.get("accounts", []) if row["id"] == selected), None)
    if not account:
        raise HTTPException(400, "请先在设置中连接 ChatGPT 账号")
    return account


def require_account(account_id: str | None = None) -> dict:
    account = _find_account(_document(), account_id)
    if not account.get("access_token") or account.get("needs_reauth"):
        raise HTTPException(401, "ChatGPT 登录已失效，请在设置中重新登录")
    if PLAN_SCOPE not in account.get("scopes", []):
        raise HTTPException(403, "此账号尚未授权使用 ChatGPT 套餐，请重新登录并允许套餐使用")
    if account.get("expires_at", 0) <= time.time() and not account.get("refresh_token"):
        raise HTTPException(401, "ChatGPT 登录已过期，请在设置中重新登录")
    return account


def public_accounts() -> dict:
    document = _document()
    return {
        "activeAccountId": document.get("active_id"),
        "accounts": [{"id": row["id"], "label": row["label"], "email": row.get("email", ""),
                      "connected": bool(row.get("access_token")) and not row.get("needs_reauth", False),
                      "planEnabled": PLAN_SCOPE in row.get("scopes", []),
                      "needsWelcome": bool(row.get("access_token")) and PLAN_SCOPE in row.get("scopes", [])
                      and not row.get("welcome_shown", False)} for row in document.get("accounts", [])],
    }


def select_account(account_id: str) -> dict:
    with _AUTH_LOCK, private_store.LOCK:
        document = _document()
        _find_account(document, account_id)
        document["active_id"] = account_id
        private_store.write_document(ACCOUNTS_FILE, document)
    return public_accounts()


def acknowledge_welcome(account_id: str) -> None:
    with _AUTH_LOCK, private_store.LOCK:
        document = _document()
        _find_account(document, account_id)["welcome_shown"] = True
        private_store.write_document(ACCOUNTS_FILE, document)


def _response_json(response: httpx.Response, message: str) -> dict:
    if response.status_code != 200:
        raise HTTPException(502, message)
    try:
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except ValueError:
        raise HTTPException(502, message) from None


def _validate_identity(client: httpx.Client, token: str, client_id: str, nonce: str | None) -> dict:
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") not in {"RS256", "ES256"} or not header.get("kid"):
            raise ValueError()
        keys = _response_json(client.get(JWKS_URL), "无法验证 ChatGPT 身份，请重新登录")
        key = next(row for row in keys["keys"] if row.get("kid") == header["kid"])
        public_key = jwt.PyJWK.from_dict(key, algorithm=header["alg"]).key
        identity = jwt.decode(token, public_key, algorithms=[header["alg"]],
                              audience=client_id, issuer=ISSUER, leeway=5,
                              options={"require": ["iss", "aud", "sub", "exp", "iat"]})
        if not isinstance(identity["sub"], str) or not identity["sub"]:
            raise ValueError()
        if nonce is not None and not secrets.compare_digest(str(identity.get("nonce", "")), nonce):
            raise ValueError()
        return identity
    except (jwt.PyJWTError, ValueError, KeyError, TypeError, StopIteration):
        raise HTTPException(400, "ChatGPT 身份验证失败，请重新发起登录") from None


def _token_fields(payload: dict, previous: dict | None = None) -> dict:
    previous = previous or {}
    try:
        access = payload["access_token"]
        refresh = payload.get("refresh_token", previous.get("refresh_token", ""))
        lifetime = float(payload["expires_in"])
        if (payload.get("token_type", "").lower() != "bearer" or not isinstance(access, str)
                or not access or any(ord(char) < 33 or ord(char) > 126 for char in access)
                or not isinstance(refresh, str) or not 0 < lifetime <= 86400):
            raise ValueError()
        scope = payload.get("scope")
        if scope is not None and not isinstance(scope, str):
            raise ValueError()
        return {"access_token": access, "refresh_token": refresh,
                "id_token": payload.get("id_token", previous.get("id_token", "")),
                "scopes": scope.split() if scope is not None else previous.get("scopes", []),
                "expires_at": time.time() + lifetime,
                "earliest_refresh_at": float(payload.get("earliest_refresh_at", 0)), "needs_reauth": False}
    except (ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(502, "ChatGPT 返回的授权信息不完整，请重新登录") from None


def access_token(account_id: str | None = None) -> str:
    # 本应用为单进程本地服务；同一进程内串行刷新，避免旋转令牌被并发使用。
    with _AUTH_LOCK:
        account = require_account(account_id)
        now = time.time()
        if account["expires_at"] > now + 60 or (account.get("earliest_refresh_at", 0) > now and account["expires_at"] > now):
            return account["access_token"]
        if not account.get("refresh_token"):
            if account["expires_at"] > now:
                return account["access_token"]
            raise HTTPException(401, "ChatGPT 登录已过期，请重新登录")
        try:
            with httpx.Client(timeout=20, follow_redirects=False) as client:
                response = client.post(TOKEN_URL, data={"grant_type": "refresh_token",
                    "client_id": account["client_id"], "refresh_token": account["refresh_token"], "resource": RESOURCE})
                if response.status_code in {400, 401, 403}:
                    with private_store.LOCK:
                        document = _document()
                        _find_account(document, account["id"])["needs_reauth"] = True
                        private_store.write_document(ACCOUNTS_FILE, document)
                    raise HTTPException(401, "ChatGPT 授权已失效，请在设置中重新登录")
                payload = _response_json(response, "暂时无法续期 ChatGPT 登录，请稍后重试")
                fields = _token_fields(payload, account)
                if payload.get("id_token"):
                    identity = _validate_identity(client, payload["id_token"], account["client_id"], None)
                    if identity["sub"] != account["subject"]:
                        raise HTTPException(401, "ChatGPT 身份不一致，请重新登录")
                if PLAN_SCOPE not in fields["scopes"]:
                    raise HTTPException(403, "ChatGPT 套餐授权已取消，请重新登录并授权")
                with private_store.LOCK:
                    document = _document()
                    _find_account(document, account["id"]).update(fields)
                    private_store.write_document(ACCOUNTS_FILE, document)
                return fields["access_token"]
        except httpx.RequestError:
            raise HTTPException(502, "无法续期 ChatGPT 登录，请检查网络后重试") from None


@dataclass
class LoginAttempt:
    id: str
    state: str = field(repr=False)
    nonce: str = field(repr=False)
    verifier: str = field(repr=False)
    host_id: str
    account: dict | None = field(repr=False)
    redirect_uri: str = ""
    status: str = "pending"
    message: str = "等待在浏览器中完成 ChatGPT 授权"
    expires_at: float = field(default_factory=lambda: time.time() + 600)
    stop: Event = field(default_factory=Event, repr=False)


_attempts: dict[str, LoginAttempt] = {}


def login_status(attempt_id: str) -> dict:
    with _AUTH_LOCK:
        attempt = _attempts.get(attempt_id)
        if not attempt:
            raise HTTPException(404, "登录请求不存在，请重新发起登录")
        if attempt.status == "pending" and time.time() >= attempt.expires_at:
            attempt.status, attempt.message = "expired", "登录等待已过期，请重新登录"
            attempt.stop.set()
        return {"id": attempt.id, "status": attempt.status, "message": attempt.message}


def cancel_login(attempt_id: str) -> None:
    with _AUTH_LOCK:
        attempt = _attempts.get(attempt_id)
        if attempt and attempt.status in {"pending", "processing"}:
            attempt.status, attempt.message = "cancelled", "已取消本次登录"
            attempt.stop.set()


def finish_login(attempt: LoginAttempt, query: dict[str, list[str]]) -> tuple[int, str]:
    with _AUTH_LOCK:
        if attempt.status != "pending" or time.time() >= attempt.expires_at:
            return 400, "此登录请求已结束或过期，请返回设置重新发起。"
        state = query.get("state", [""])[0]
        if not secrets.compare_digest(state.encode("utf-8"), attempt.state.encode("ascii")):
            return 400, "登录校验未通过，请使用本次登录打开的授权页面。"
        if query.get("error"):
            attempt.status, attempt.message = "failed", "ChatGPT 授权未完成或已取消，请返回设置重试"
            attempt.stop.set()
            return 400, attempt.message
        client_id = query.get("client_id", [""])[0]
        if attempt.account:
            if client_id and client_id != attempt.account["client_id"]:
                return 400, "返回的账号连接不匹配，请重新登录。"
            client_id = attempt.account["client_id"]
        code = query.get("code", [""])[0]
        if not code or not client_id or client_id == "dynamic_agent_client" or len(client_id) > 300:
            return 400, "ChatGPT 注册信息不完整，请重新登录。"
        attempt.status = "processing"
    try:
        with httpx.Client(timeout=20, follow_redirects=False) as client:
            payload = _response_json(client.post(TOKEN_URL, data={
                "grant_type": "authorization_code", "client_id": client_id, "code": code,
                "code_verifier": attempt.verifier, "redirect_uri": attempt.redirect_uri, "resource": RESOURCE,
            }), "ChatGPT 授权交换失败，请返回设置重新登录")
            identity = _validate_identity(client, payload.get("id_token", ""), client_id, attempt.nonce)
            if attempt.account and identity["sub"] != attempt.account["subject"]:
                raise HTTPException(400, "登录的账号与所选连接不一致，请使用新增账号入口")
            fields = _token_fields(payload)
        with _AUTH_LOCK, private_store.LOCK:
            if attempt.stop.is_set() or attempt.status != "processing":
                return 400, "本次登录已取消，请返回设置。"
            document = _document()
            accounts = document.setdefault("accounts", [])
            account = next((row for row in accounts if row["client_id"] == client_id and row["subject"] == identity["sub"]), None)
            if account is None:
                account = {"id": str(uuid4()), "client_id": client_id, "subject": identity["sub"],
                           "label": f"连接 {len(accounts) + 1}", "welcome_shown": False}
                accounts.append(account)
            account.update(fields)
            account["email"] = identity.get("email", "") if isinstance(identity.get("email", ""), str) else ""
            document["active_id"] = account["id"]
            private_store.write_document(ACCOUNTS_FILE, document)
            attempt.status = "completed"
            attempt.message = "ChatGPT 已连接，请选择模型、测试连接并保存"
            if PLAN_SCOPE not in fields["scopes"]:
                attempt.message = "账号已连接，但尚未授权套餐使用，请重新登录并允许套餐使用"
            return 200, attempt.message + "。可以关闭此页面，返回应用设置。"
    except HTTPException as error:
        with _AUTH_LOCK:
            if not attempt.stop.is_set():
                attempt.status, attempt.message = "failed", error.detail
        return 400, "登录未完成，请返回应用设置查看提示并重试。"
    except Exception:
        # 回调服务不记录请求、授权码、异常正文或令牌。
        with _AUTH_LOCK:
            if not attempt.stop.is_set():
                attempt.status, attempt.message = "failed", "ChatGPT 登录失败，请检查网络后重新登录"
        return 400, "登录未完成，请返回应用设置重试。"
    finally:
        attempt.stop.set()


class _CallbackServer(HTTPServer):
    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(5)
        return connection, address


def start_login(account_id: str | None = None) -> dict:
    with _AUTH_LOCK, private_store.LOCK:
        document = _document()
        account = _find_account(document, account_id) if account_id else None
        if "host_id" not in document:
            document["host_id"] = f"urn:uuid:{uuid4()}"
            private_store.write_document(ACCOUNTS_FILE, document)
        for old in list(_attempts.values()):
            if old.status in {"pending", "processing"}:
                cancel_login(old.id)
            if old.expires_at < time.time() - 600:
                _attempts.pop(old.id, None)
        while len(_attempts) >= 16:
            _attempts.pop(next(iter(_attempts)))
        attempt = LoginAttempt(secrets.token_urlsafe(24), secrets.token_urlsafe(32), secrets.token_urlsafe(32),
                               secrets.token_urlsafe(48), document["host_id"], account)

        class Callback(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                url = urlsplit(self.path)
                if (url.path != "/auth/callback" or len(self.path) > 16000
                        or self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}"):
                    self.send_error(404)
                    return
                status, message = finish_login(attempt, parse_qs(url.query))
                content = ("<!doctype html><html lang='zh-CN'><meta charset='utf-8'><title>ChatGPT 登录</title>"
                           "<body><h2>ChatGPT 登录</h2><p>" + message + "</p></body></html>").encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Referrer-Policy", "no-referrer")
                self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
                self.end_headers()
                self.wfile.write(content)

        try:
            server = _CallbackServer(("127.0.0.1", 0), Callback)
        except OSError:
            raise HTTPException(503, "无法启动本机登录回调，请检查本机端口权限") from None
        server.timeout = 1
        attempt.redirect_uri = f"http://127.0.0.1:{server.server_port}/auth/callback"
        _attempts[attempt.id] = attempt

        def listen():
            try:
                while not attempt.stop.is_set() and time.time() < attempt.expires_at:
                    server.handle_request()
            finally:
                server.server_close()

        Thread(target=listen, name="chatgpt-oauth-callback", daemon=True).start()
        challenge = base64.urlsafe_b64encode(hashlib.sha256(attempt.verifier.encode()).digest()).decode().rstrip("=")
        parameters = {"client_id": account["client_id"] if account else "dynamic_agent_client",
            "ext_agent_host_id": attempt.host_id, "response_type": "code", "redirect_uri": attempt.redirect_uri,
            "scope": SCOPES, "resource": RESOURCE, "state": attempt.state, "nonce": attempt.nonce,
            "code_challenge_method": "S256", "code_challenge": challenge}
        if not account:
            parameters["agent_name_hint"] = "Personal App"
        return {"attemptId": attempt.id, "authorizationUrl": AUTHORIZE_URL + "?" + urlencode(parameters),
                "expiresAt": attempt.expires_at}


def disconnect(account_id: str) -> dict:
    with _AUTH_LOCK:
        for attempt in list(_attempts.values()):
            cancel_login(attempt.id)
        document = _document()
        account = _find_account(document, account_id)
        confirmed = not bool(account.get("refresh_token"))
        if account.get("refresh_token"):
            try:
                with httpx.Client(timeout=10, follow_redirects=False) as client:
                    discovery = _response_json(client.get(f"{ISSUER}/.well-known/openid-configuration"), "无法确认远端撤销")
                    endpoint = discovery.get("revocation_endpoint", "")
                    parsed = urlsplit(endpoint)
                    if parsed.scheme == "https" and parsed.netloc == "auth.openai.com" and not parsed.query and not parsed.fragment:
                        confirmed = client.post(endpoint, data={"token": account["refresh_token"],
                            "token_type_hint": "refresh_token", "client_id": account["client_id"]}).status_code == 200
            except (httpx.RequestError, HTTPException, ValueError):
                confirmed = False
        with private_store.LOCK:
            document = _document()
            account = _find_account(document, account_id)
            for key in ("access_token", "refresh_token", "id_token", "scopes", "expires_at", "earliest_refresh_at"):
                account.pop(key, None)
            private_store.write_document(ACCOUNTS_FILE, document)
        return {"ok": True, "revocationConfirmed": confirmed}
