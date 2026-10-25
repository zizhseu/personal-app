"""固定版本的本机小红书采集服务：校验下载、启动、状态和安全停止。"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

from app.core import config, private_store

RUNTIME = config.BASE_DIR.parent / ".runtime" / "xhs"
EXECUTABLE = RUNTIME / "xiaohongshu-mcp-windows-amd64.exe"
STATUS_FILE = RUNTIME / "startup.json"
VERSION = "v2.5.5"
DOWNLOAD_URL = f"https://github.com/xpzouying/xiaohongshu-mcp/releases/download/{VERSION}/{EXECUTABLE.name}"
EXPECTED_SHA256 = "cb55674f90c1649c875be9c4cde3af193b02fc34ffc860c40c8d711e6ca53e27"


def read_status() -> dict:
    try:
        value = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
        if value["status"] == "starting" and time.time() - value.get("updatedAt", 0) > 10:
            worker = value.get("workerPid")
            if time.time() - value.get("updatedAt", 0) > 660 or not isinstance(worker, int) or _process_path(worker) != Path(sys.executable).resolve():
                return {**value, "status": "failed", "message": "上次组件启动已中断，可以重新启动"}
        if value["status"] == "ready" and value.get("pid") and not _owned_pid(value["pid"]):
            return {**value, "status": "failed", "message": "本机采集组件已停止，可以重新启动"}
        return value
    except (OSError, ValueError, KeyError, TypeError):
        return {"status": "idle", "message": "尚未启动本机采集服务"}


def write_status(status: str, message: str, **extra):
    RUNTIME.mkdir(parents=True, exist_ok=True)
    value = {"status": status, "message": message, "updatedAt": time.time(), **extra}
    temporary = STATUS_FILE.with_suffix(f".{os.getpid()}.{secrets.token_hex(4)}.tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, STATUS_FILE)
    finally:
        temporary.unlink(missing_ok=True)


def _process_path(pid: int) -> Path | None:
    from ctypes import wintypes

    if os.name != "nt" or not isinstance(pid, int) or pid <= 0:
        return None
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        length = wintypes.DWORD(32768)
        path = ctypes.create_unicode_buffer(length.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(length)):
            return None
        return Path(path.value).resolve()
    finally:
        kernel.CloseHandle(handle)


def _owned_pid(pid: int) -> bool:
    return _process_path(pid) == EXECUTABLE.resolve()


def _stop_owned_process(pid: int) -> bool:
    from ctypes import wintypes

    if not _owned_pid(pid):
        return False
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
    kernel.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    handle = kernel.OpenProcess(0x1000 | 0x0001 | 0x100000, False, pid)
    if not handle:
        return False
    try:
        # 在将要停止的同一进程句柄上复核，避免 PID 被重用后误停其他应用。
        length = wintypes.DWORD(32768)
        path = ctypes.create_unicode_buffer(length.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(length)) or Path(path.value).resolve() != EXECUTABLE.resolve():
            return False
        if not kernel.TerminateProcess(handle, 0):
            return False
        return kernel.WaitForSingleObject(handle, 5000) == 0
    finally:
        kernel.CloseHandle(handle)


def stop():
    state = read_status()
    write_status("stopped", "已停止本应用管理的采集服务")
    if isinstance(state.get("pid"), int):
        _stop_owned_process(state["pid"])


def child_environment(token: str) -> dict:
    environment = dict(os.environ)
    environment["AUTH_TOKEN"] = token
    environment["COOKIES_PATH"] = str(config.DATA_DIR / "xhs" / "cookies.json")
    # 仅为采集子进程指定独立缓存和临时目录，不修改系统环境或用户浏览器。
    # 原下载缓存曾出现 Windows SideBySide 错误；项目内副本已实际启动验证。
    for variable, folder in (("LOCALAPPDATA", RUNTIME / "cache"), ("TEMP", RUNTIME / "temp"), ("TMP", RUNTIME / "temp")):
        folder.mkdir(parents=True, exist_ok=True)
        environment[variable] = str(folder)
    (config.DATA_DIR / "xhs").mkdir(parents=True, exist_ok=True)
    return environment


def prepare():
    import httpx

    if EXECUTABLE.exists() and hashlib.sha256(EXECUTABLE.read_bytes()).hexdigest() == EXPECTED_SHA256:
        return
    write_status("starting", "正在下载并校验采集组件…", workerPid=os.getpid())
    temporary = EXECUTABLE.with_suffix(".download")
    digest, count = hashlib.sha256(), 0
    try:
        with httpx.Client(timeout=180, follow_redirects=True) as client, client.stream("GET", DOWNLOAD_URL) as response:
            response.raise_for_status()
            with temporary.open("wb") as stream:
                for chunk in response.iter_bytes():
                    count += len(chunk)
                    if count > 40_000_000:
                        raise RuntimeError("下载大小异常")
                    digest.update(chunk)
                    stream.write(chunk)
        if digest.hexdigest() != EXPECTED_SHA256:
            raise RuntimeError("下载校验失败")
        os.replace(temporary, EXECUTABLE)
    finally:
        temporary.unlink(missing_ok=True)


def start():
    import httpx

    if os.name != "nt":
        raise RuntimeError("一键启动目前支持 Windows；其他系统可自行运行 xiaohongshu-mcp 后配置连接地址")
    RUNTIME.mkdir(parents=True, exist_ok=True)
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = private_store.read_document("experience-collector.private")
    if data.get("url", "http://127.0.0.1:18060") != "http://127.0.0.1:18060":
        raise RuntimeError("自定义采集服务请自行启动，或先将地址恢复为 http://127.0.0.1:18060")
    with httpx.Client(trust_env=False, timeout=2) as client:
        try:
            health = client.get("http://127.0.0.1:18060/health")
            if health.status_code == 200 and health.json().get("data", {}).get("service") == "xiaohongshu-mcp":
                previous_pid = read_status().get("pid")
                extra = {"pid": previous_pid} if isinstance(previous_pid, int) and _owned_pid(previous_pid) else {}
                write_status("ready", "采集组件已运行，可以获取二维码或检查登录", **extra)
                return
        except (httpx.RequestError, ValueError):
            pass
    previous_pid = read_status().get("pid")
    if isinstance(previous_pid, int) and _owned_pid(previous_pid):
        _stop_owned_process(previous_pid)
    write_status("starting", "正在准备本机采集服务…", workerPid=os.getpid())
    prepare()
    if read_status().get("status") == "stopped":
        return
    secret = data.get("token") or secrets.token_urlsafe(32)
    private_store.write_document("experience-collector.private", {"url": "http://127.0.0.1:18060", "token": secret})
    environment = child_environment(secret)
    with (RUNTIME / "service.log").open("ab") as output:
        process = subprocess.Popen([str(EXECUTABLE), "-port=127.0.0.1:18060", "-headless=true"], cwd=RUNTIME,
            env=environment, stdin=subprocess.DEVNULL, stdout=output, stderr=output,
            creationflags=subprocess.CREATE_NO_WINDOW)
    write_status("starting", "正在准备采集浏览器，首次启动可能需要数分钟…", pid=process.pid, workerPid=os.getpid())
    with httpx.Client(trust_env=False, timeout=2) as client:
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            if read_status().get("status") == "stopped":
                _stop_owned_process(process.pid)
                return
            if process.poll() is not None:
                raise RuntimeError("采集服务未能启动，可重试；启动日志保存在本机 .runtime/xhs/service.log")
            try:
                response = client.get("http://127.0.0.1:18060/health")
                if response.status_code == 200 and response.json().get("data", {}).get("service") == "xiaohongshu-mcp":
                    write_status("ready", "采集组件已启动，可以获取二维码或检查登录", pid=process.pid)
                    return
            except (httpx.RequestError, ValueError):
                pass
            time.sleep(1)
    _stop_owned_process(process.pid)
    write_status("failed", "采集组件准备超时，已停止本次启动，可以检查网络后重试")
