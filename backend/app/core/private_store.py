"""单机私有配置：原子写入，Windows 使用当前用户的 DPAPI 保护内容。"""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import tempfile
from threading import RLock

from fastapi import HTTPException

from app.core import config

LOCK = RLock()
_HEADER = b"PERSONAL-APP-DPAPI\x00"


def _dpapi(content: bytes, *, decrypt: bool = False) -> bytes:
    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(content)
    source = Blob(len(content), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    library = ctypes.WinDLL("crypt32", use_last_error=True)
    function = library.CryptUnprotectData if decrypt else library.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise OSError("无法访问当前用户的私有配置")
    try:
        return ctypes.string_at(target.data, target.size)
    finally:
        free = ctypes.WinDLL("kernel32", use_last_error=True).LocalFree
        free.argtypes = [ctypes.c_void_p]
        free.restype = ctypes.c_void_p
        free(target.data)


def read_document(name: str) -> dict:
    with LOCK:
        path = config.DATA_DIR / name
        try:
            content = path.read_bytes()
        except FileNotFoundError:
            return {}
        except OSError:
            raise HTTPException(500, "无法读取本机模型配置，请检查数据目录权限") from None
        try:
            if content.startswith(_HEADER):
                if os.name != "nt":
                    raise ValueError("该配置属于另一台 Windows 设备")
                content = _dpapi(content[len(_HEADER):], decrypt=True)
            result = json.loads(content)
            if not isinstance(result, dict):
                raise ValueError("配置格式错误")
            return result
        except (OSError, ValueError, TypeError):
            raise HTTPException(500, "本机模型配置无法解密或已损坏，请恢复本机备份后重试") from None


def write_document(name: str, document: dict) -> None:
    with LOCK:
        temporary: Path | None = None
        try:
            config.DATA_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
            content = json.dumps(document, ensure_ascii=False).encode("utf-8")
            if os.name == "nt":
                content = _HEADER + _dpapi(content)
            descriptor, filename = tempfile.mkstemp(prefix=".private-", dir=config.DATA_DIR)
            temporary = Path(filename)
            with os.fdopen(descriptor, "wb") as stream:
                os.chmod(temporary, 0o600)
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, config.DATA_DIR / name)
        except (OSError, ValueError):
            raise HTTPException(500, "无法保存本机模型配置，请检查数据目录权限") from None
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink(missing_ok=True)
