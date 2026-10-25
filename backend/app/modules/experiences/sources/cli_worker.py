"""固定版本 CLI 的进程内桥接。仅支持登录、搜索、读取，不开放写操作或任意命令。"""
import base64
from contextlib import redirect_stdout, redirect_stderr
from io import BytesIO
from importlib.metadata import version
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from app.core import config

config.DATA_DIR = Path(os.environ["PERSONAL_APP_SOURCE_DATA"]).resolve()
from app.core import private_store

COOKIE_FILE = "experience-cli-cookies.private"
QR_FILE = "experience-cli-qr.private"
INSTALL_FILE = "experience-cli-install.private"
_job = None


def contain_process_tree():
    global _job
    if os.name == "nt":
        # 首次安装也可使用：不依赖尚未安装的 pywin32。
        import ctypes
        from ctypes import wintypes
        class BasicLimits(ctypes.Structure):
            _fields_ = [("processTime", ctypes.c_longlong), ("jobTime", ctypes.c_longlong), ("flags", wintypes.DWORD),
                ("minWorkingSet", ctypes.c_size_t), ("maxWorkingSet", ctypes.c_size_t), ("activeLimit", wintypes.DWORD),
                ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD), ("scheduling", wintypes.DWORD)]
        class ExtendedLimits(ctypes.Structure):
            _fields_ = [("basic", BasicLimits), ("io", ctypes.c_ulonglong * 6), ("processMemory", ctypes.c_size_t),
                ("jobMemory", ctypes.c_size_t), ("peakProcess", ctypes.c_size_t), ("peakJob", ctypes.c_size_t)]
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel.CreateJobObjectW.restype = wintypes.HANDLE
        kernel.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        kernel.SetInformationJobObject.restype = wintypes.BOOL
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel.AssignProcessToJobObject.restype = wintypes.BOOL
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        _job = kernel.CreateJobObjectW(None, None)
        if not _job:
            raise ctypes.WinError(ctypes.get_last_error())
        limits = ExtendedLimits()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(_job, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(_job, kernel.GetCurrentProcess()):
            code = ctypes.get_last_error()
            kernel.CloseHandle(_job)
            _job = None
            raise ctypes.WinError(code)


def configure_browser():
    from camoufox import pkgman, multiversion
    # 二进制可由本项目的多个资料库复用；账号和浏览器临时资料仍分开。
    root = config.BASE_DIR.parent / ".runtime" / "xhs-cli" / "browser"
    root.mkdir(parents=True, exist_ok=True)
    pkgman.INSTALL_DIR = root
    multiversion.INSTALL_DIR = root
    for key, name in {"BROWSERS_DIR": "browsers", "CONFIG_FILE": "config.json", "REPO_CACHE_FILE": "repo_cache.json", "COMPAT_FLAG": ".0.5_FLAG"}.items():
        setattr(multiversion, key, root / name)
    return pkgman


def install():
    private_store.write_document(INSTALL_FILE, {"status": "starting", "message": "正在安装接口采集组件…", "updatedAt": time.time()})
    requirements = config.BASE_DIR / "requirements-collectors.txt"
    subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(requirements), "--disable-pip-version-check"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=900, check=True)
    private_store.write_document(INSTALL_FILE, {"status": "starting", "message": "正在准备独立扫码浏览器，首次下载可能需要几分钟…", "updatedAt": time.time()})
    pkgman = configure_browser()
    try:
        pkgman.launch_path()
    except Exception:
        if sys.platform == "win32":
            # 固定官方发布资产，避免依赖易被限流的 GitHub releases API。
            asset = pkgman.AvailableVersion(version=pkgman.Version(build="beta.36", version="156.0.1"),
                url="https://github.com/daijro/camoufox/releases/download/v156.0.1-beta.36/camoufox-156.0.1-beta.36-win.x86_64.zip",
                is_prerelease=False, sha256="096fd4832a7a32f2aa7f7bdd07fe6253dda296cbe783acd7bc2c86cf5ae62031")
            pkgman.CamoufoxFetcher(selected_version=asset).install()
        else:
            pkgman.CamoufoxFetcher().install()
    pkgman.launch_path()
    private_store.write_document(INSTALL_FILE, {"status": "ready", "message": "接口采集组件已就绪，可以扫码登录", "updatedAt": time.time()})
    return {"ready": True}


def load_sdk():
    if version("xiaohongshu-cli") != "0.6.4" or version("camoufox") != "0.5.8":
        raise RuntimeError("version")
    import xhs_cli.cookies as cookies_module
    state = config.DATA_DIR / "xhs-cli" / "state"
    state.mkdir(parents=True, exist_ok=True)
    cookies_module.get_config_dir = lambda: state
    cookies_module.save_cookies = lambda values: private_store.write_document(COOKIE_FILE, dict(values))
    cookies_module.load_saved_cookies = lambda: private_store.read_document(COOKIE_FILE) or None
    from xhs_cli.client import XhsClient
    import xhs_cli.client_mixins as mixins
    # 搜索引用由本应用加密管理，不让 SDK 再向公共用户目录写 token 缓存。
    mixins.cache_note_context = lambda *args, **kwargs: None
    mixins.get_cached_note_context = lambda *args, **kwargs: {}
    mixins.invalidate_note_context = lambda *args, **kwargs: None
    return XhsClient


def login():
    import xhs_cli.qr_login as qr
    from camoufox import sync_api
    pkgman = configure_browser()
    browser_class = sync_api.Camoufox
    # 不打开桌面窗口，将二维码直接呈现在本应用中。
    sync_api.Camoufox = lambda **kwargs: browser_class(**{**kwargs, "headless": True})
    qr._ensure_camoufox_ready = lambda: pkgman.launch_path()

    def display(url):
        import qrcode
        stream = BytesIO()
        qrcode.make(url).save(stream, format="PNG")
        image = "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii")
        private_store.write_document(QR_FILE, {"status": "waiting", "image": image, "expires": time.time() + 240})
        return True

    qr._display_qr_in_terminal = display
    values = qr.qrcode_login(prefer_browser_assisted=True, timeout_s=240)
    private_store.write_document(COOKIE_FILE, values)
    private_store.write_document("experience-cli-session.private", {"id": str(uuid4())})
    private_store.write_document(QR_FILE, {"status": "succeeded", "expires": time.time()})
    return {"loggedIn": True}


def dispatch(data):
    op = data.get("op")
    if op == "install":
        return install()
    client_type = load_sdk()
    if op == "login":
        return login()
    values = private_store.read_document(COOKIE_FILE)
    if not values:
        return {"loggedIn": False} if op == "status" else {"loginRequired": True}
    from xhs_cli.exceptions import SessionExpiredError
    with client_type(values, timeout=25, request_delay=1.2, max_retries=1) as client:
        try:
            if op == "status":
                from xhs_cli.command_normalizers import normalize_xhs_user_payload
                user = normalize_xhs_user_payload(client.get_self_info())
                logged_in = bool(user["id"] and not user["guest"] and user["nickname"] != "Unknown")
                # 状态检查也可能收到服务端轮换的 Cookie；仅有效账号响应才回写。
                if logged_in:
                    private_store.write_document(COOKIE_FILE, client.cookies)
                return {"loggedIn": logged_in}
            if op == "search":
                result = client.search_notes(keyword=data["keyword"], sort=data["sort"], note_type=2, page=1, page_size=20)
            elif op == "detail":
                result = client.get_note_detail(data["id"], xsec_token=data["token"], xsec_source="pc_search")
            else:
                raise ValueError("operation")
            private_store.write_document(COOKIE_FILE, client.cookies)
            return result
        except SessionExpiredError:
            return {"loggedIn": False} if op == "status" else {"loginRequired": True}


def main():
    data = json.loads(sys.stdin.read(100_000))
    try:
        contain_process_tree()
        with open(os.devnull, "w", encoding="utf-8") as sink, redirect_stdout(sink), redirect_stderr(sink):
            result = dispatch(data)
        output = {"ok": True, "data": result}
    except Exception as error:
        name = type(error).__name__
        message = {"NeedVerifyError": "平台要求验证，请先在小红书中完成验证后重试", "SessionExpiredError": "登录已过期，请重新扫码",
                   "IpBlockedError": "平台暂时限制当前网络，请稍后重试", "SignatureError": "接口签名不兼容，请检查采集组件版本",
                   "PackageNotFoundError": "接口采集组件未安装，请先安装组件", "FileNotFoundError": "独立扫码浏览器未就绪，请先安装组件"}.get(name,
                   "接口采集未完成，请检查组件安装、登录状态和网络后重试")
        if data.get("op") == "install":
            private_store.write_document(INSTALL_FILE, {"status": "failed", "message": message, "updatedAt": time.time()})
        if data.get("op") == "login":
            private_store.write_document(QR_FILE, {"status": "failed", "message": message, "expires": time.time()})
        output = {"ok": False, "message": message, "kind": name}
    sys.stdout.write(json.dumps(output, ensure_ascii=True))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
