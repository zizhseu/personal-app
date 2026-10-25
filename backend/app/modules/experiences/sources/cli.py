"""用固定 SDK 子进程适配 xiaohongshu-cli，独立凭据，不读取系统浏览器 Cookie。"""
import asyncio
from datetime import datetime, timezone
from importlib.metadata import version, PackageNotFoundError
import json
import os
import subprocess
import sys
import time

from fastapi import HTTPException

from app.core import config, private_store
from .assets import image_url
from .contracts import Capabilities, SearchResult

COOKIE_FILE = "experience-cli-cookies.private"
QR_FILE = "experience-cli-qr.private"
INSTALL_FILE = "experience-cli-install.private"
_jobs: dict[tuple[str, str], asyncio.Task] = {}
_gate = asyncio.Lock()


def installed():
    try:
        return version("xiaohongshu-cli") == "0.6.4" and version("camoufox") == "0.5.8"
    except PackageNotFoundError:
        return False


def active(op):
    task = _jobs.get((str(config.DATA_DIR), op))
    return task is not None and not task.done()


async def execute(op, **arguments):
    env = dict(os.environ, PERSONAL_APP_SOURCE_DATA=str(config.DATA_DIR), PYTHONIOENCODING="utf-8")
    # Windows 的 Uvicorn reload 使用 SelectorEventLoop，不支持异步子进程。
    # 用线程等待 Popen，仍保持请求可取消和超时控制。
    try:
        process = subprocess.Popen([sys.executable, "-m", "app.modules.experiences.sources.cli_worker"],
            cwd=config.BASE_DIR, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            **({"creationflags": 0x08000000} if os.name == "nt" else {}))
    except OSError:
        raise HTTPException(503, "无法启动接口采集组件，请检查安装后重试") from None
    try:
        async with asyncio.timeout(1500 if op == "install" else 300 if op == "login" else 100):
            output, _ = await asyncio.to_thread(process.communicate, json.dumps({"op": op, **arguments}).encode())
        if len(output) > 5_000_000:
            raise ValueError()
        body = json.loads(output)
        if not body.get("ok"):
            raise HTTPException(502, body.get("message", "接口采集未完成，请稍后重试"))
        result = body["data"]
        if not isinstance(result, dict):
            raise ValueError()
        if result.get("loginRequired"):
            raise HTTPException(401, "接口采集尚未登录，请先扫码登录")
        return result
    except TimeoutError:
        raise HTTPException(504, "接口采集超时，请稍后重试") from None
    except (ValueError, KeyError, UnicodeError):
        raise HTTPException(502, "采集组件返回格式不兼容，请重新安装固定版本组件") from None
    finally:
        if process.poll() is None:
            process.terminate()
            await asyncio.to_thread(process.wait, timeout=10)


def spawn(op):
    key = (str(config.DATA_DIR), op)
    async def run():
        try:
            await execute(op)
        except Exception as error:
            name = INSTALL_FILE if op == "install" else QR_FILE
            message = error.detail if isinstance(error, HTTPException) and isinstance(error.detail, str) else "采集组件未完成准备，请检查安装和网络后重试"
            private_store.write_document(name, {"status": "failed", "message": message, "expires": time.time()})
    task = asyncio.create_task(run())
    _jobs[key] = task
    return task


def _url(image):
    if not isinstance(image, dict):
        return ""
    candidates = [image.get(key) for key in ("url_default", "urlDefault", "url_pre", "urlPre", "url")]
    info = image.get("info_list") or image.get("infoList") or []
    if isinstance(info, list):
        candidates += [entry.get("url") for entry in info if isinstance(entry, dict)]
    return next((safe for value in candidates if value and (safe := image_url(value))), "")


class CliProvider:
    id = "xhs-cli"
    platform = "xiaohongshu"
    label = "接口采集（CLI）"
    description = "使用 xiaohongshu-cli 的签名接口搜索和读取图文笔记；扫码时使用独立浏览器。"
    homepage = "https://github.com/jackwener/xiaohongshu-cli"
    capabilities = Capabilities(sorts=("综合", "最新", "热度"))

    def availability(self):
        return {"installed": installed(), "version": "0.6.4"}

    def connection(self):
        return {"url": "", "tokenConfigured": False, **self.availability()}

    def save_connection(self, payload):
        raise HTTPException(400, "接口采集使用独立扫码登录，不需要服务地址或鉴权令牌")

    async def start(self):
        if active("login"):
            raise HTTPException(409, "正在扫码登录，请完成登录或等待二维码过期后再安装")
        if not active("install"):
            private_store.write_document(INSTALL_FILE, {"status": "starting", "message": "正在准备接口采集组件…", "updatedAt": time.time()})
            spawn("install")
        return {"started": True, "message": "已开始准备接口采集组件和独立扫码浏览器"}

    def startup_status(self):
        state = private_store.read_document(INSTALL_FILE)
        if state.get("status") == "starting" and not active("install"):
            return {"status": "failed", "message": "安装已中断，请重新安装组件"}
        return {"status": state.get("status", "idle"), "message": state.get("message", "请先安装接口采集组件及独立扫码浏览器")}

    async def login_status(self):
        if active("login"):
            return {"loggedIn": False}
        if not private_store.read_document(COOKIE_FILE):
            state = private_store.read_document(QR_FILE)
            if state.get("status") == "failed":
                raise HTTPException(502, state.get("message", "扫码登录未完成，请重新获取二维码"))
            return {"loggedIn": False}
        async with _gate:
            return await execute("status")

    async def login_qrcode(self):
        if not installed():
            raise HTTPException(503, "接口采集组件未安装，请先安装组件")
        if active("install"):
            raise HTTPException(409, "组件正在安装，请等待安装完成")
        state = private_store.read_document(QR_FILE)
        if active("login") and state.get("expires", 0) <= time.time() and state.get("status") == "waiting":
            task = _jobs[(str(config.DATA_DIR), "login")]
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        if not active("login"):
            private_store.write_document(QR_FILE, {"status": "starting", "expires": time.time() + 60})
            spawn("login")
        for _ in range(225):
            state = private_store.read_document(QR_FILE)
            if state.get("status") == "waiting":
                return {"loggedIn": False, "image": state.get("image", ""), "timeout": str(max(1, int(state["expires"] - time.time())))}
            if state.get("status") == "succeeded":
                return {"loggedIn": True, "image": "", "timeout": "0"}
            if state.get("status") == "failed":
                raise HTTPException(502, state.get("message", "二维码获取失败，请重新安装组件后重试"))
            await asyncio.sleep(0.2)
        raise HTTPException(504, "扫码页面准备超时，请稍后重新获取二维码")

    async def search(self, keyword, sort, period):
        session = private_store.read_document("experience-cli-session.private").get("id", "")
        async with _gate:
            data = await execute("search", keyword=keyword, sort={"综合": "general", "最新": "time_descending", "热度": "popularity_descending"}[sort])
        if session != private_store.read_document("experience-cli-session.private").get("id", ""):
            raise HTTPException(409, "登录状态在搜索期间发生变化，请重新搜索")
        items = data.get("items")
        if not isinstance(items, list):
            raise HTTPException(502, "接口采集没有返回搜索列表，请检查登录状态")
        hits = []
        for item in items[:40]:
            if not isinstance(item, dict):
                continue
            card = item.get("note_card") or item.get("noteCard") or {}
            if not isinstance(card, dict):
                continue
            note_id = item.get("id") or card.get("note_id")
            token = item.get("xsec_token") or item.get("xsecToken") or card.get("xsec_token")
            if (not isinstance(note_id, str) or not note_id.isalnum() or not isinstance(token, str) or not token
                    or card.get("type", "normal") not in {"normal", "image"}):
                continue
            user = card.get("user") or {}
            info = card.get("interact_info") or card.get("interactInfo") or {}
            if not isinstance(user, dict) or not isinstance(info, dict):
                continue
            hits.append(SearchResult({"sourceId": note_id, "title": str(card.get("display_title") or card.get("displayTitle") or card.get("title") or "未命名笔记")[:300],
                "author": str(user.get("nickname") or "")[:100], "cover": _url(card.get("cover") or {}),
                "likes": str(info.get("liked_count") or info.get("likedCount") or ""), "sourceUrl": f"https://www.xiaohongshu.com/explore/{note_id}"},
                {"id": note_id, "token": token, "session": session}))
        return hits

    async def fetch(self, locator):
        if locator.get("session", "") != private_store.read_document("experience-cli-session.private").get("id", ""):
            raise HTTPException(409, "接口采集的登录账号已更改，请重新搜索后采集")
        async with _gate:
            result = await execute("detail", id=locator["id"], token=locator["token"])
        try:
            if "items" in result:
                note = result["items"][0]
                note = note.get("note_card") or note.get("noteCard") or note
            else:
                note = result.get("note") or result
            source_id = note.get("note_id") or note.get("noteId") or note.get("id")
            if source_id != locator["id"] or not isinstance(note.get("desc", ""), str):
                raise ValueError()
            images = note.get("image_list") or note.get("imageList") or []
            if not isinstance(images, list) or len(images) > 30:
                raise ValueError()
            normalized = []
            for index, image in enumerate(images):
                url = _url(image)
                normalized.append({"id": f"image-{index + 1}", "url": url, "status": "pending" if url else "failed", "error": None if url else "图片地址不可用"})
            published = note.get("time")
            published_at = datetime.fromtimestamp(published / 1000, timezone.utc).isoformat() if isinstance(published, (int, float)) and 0 < published < 10**14 else None
            return {"platform": self.platform, "source_id": source_id, "source_url": f"https://www.xiaohongshu.com/explore/{source_id}",
                "title": str(note.get("title") or "未命名笔记")[:300], "author": str((note.get("user") or {}).get("nickname") or "")[:100],
                "raw_body": note.get("desc", "")[:60000], "published_at": published_at, "images": normalized}
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, OSError):
            raise HTTPException(502, "接口笔记详情不完整或与搜索结果不匹配，请重新搜索") from None
