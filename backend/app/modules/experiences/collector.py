"""只调用本机采集服务的登录与读取接口；不把网页内容交给模型决定调用什么工具。"""
import asyncio
from datetime import datetime, timezone
import ipaddress
import secrets
import time
from urllib.parse import urlsplit

from fastapi import HTTPException
import httpx

from app.core import private_store

CONNECTION_FILE = "experience-collector.private"
SEARCH_FILE = "experience-search.private"
_gate = asyncio.Lock()


def connection() -> tuple[str, str]:
    data = private_store.read_document(CONNECTION_FILE)
    return data.get("url", "http://127.0.0.1:18060"), data.get("token", "")


def save_connection(payload: dict) -> dict:
    value = str(payload.get("url", "")).strip().rstrip("/")
    try:
        url = urlsplit(value)
        if (url.scheme != "http" or not ipaddress.ip_address(url.hostname or "").is_loopback or not url.port
                or url.username is not None or url.password is not None or url.path or url.query or url.fragment):
            raise ValueError()
        old_url, old_token = connection()
        token = payload.get("token")
        if token is not None and (not isinstance(token, str) or len(token) > 8192 or any(ord(c) < 33 or ord(c) > 126 for c in token)):
            raise ValueError()
        secret = "" if payload.get("clearToken") else (token or (old_token if old_url == value else ""))
        private_store.write_document(CONNECTION_FILE, {"url": value, "token": secret})
        return {"url": value, "tokenConfigured": bool(secret)}
    except (ValueError, TypeError):
        raise HTTPException(400, "请填写本机采集服务地址，例如 http://127.0.0.1:18060，鉴权令牌不能含空白字符") from None


async def call(method: str, path: str, data: dict | None = None) -> dict:
    url, token = connection()
    try:
        async with asyncio.timeout(100):
            # 搜索、详情和扫码共享浏览器会话，串行读取，避免相互打断。
            async with _gate:
                async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=5), trust_env=False, follow_redirects=False) as client:
                    response = await client.request(method, url + path, json=data,
                        headers={"Authorization": f"Bearer {token}"} if token else {})
        if response.status_code in {401, 403}:
            raise HTTPException(502, "采集服务鉴权失败，请检查连接令牌；如页面要求验证，请在小红书中完成验证")
        if response.status_code != 200:
            raise HTTPException(502, "小红书读取未完成，请检查登录状态后重试；原有资料保留")
        body = response.json()
        if body.get("success") is not True or not isinstance(body.get("data"), dict):
            raise ValueError()
        return body["data"]
    except (TimeoutError, httpx.TimeoutException):
        raise HTTPException(504, "采集服务响应超时，请稍后重试；如需要登录或验证，请先处理登录状态") from None
    except httpx.RequestError:
        raise HTTPException(503, "无法连接本机小红书采集服务，请先启动采集服务") from None
    except (ValueError, AttributeError):
        raise HTTPException(502, "采集服务返回格式不兼容，请检查服务版本和登录状态") from None


def image_url(value: str) -> str:
    try:
        url = urlsplit(value)
        hostname = url.hostname or ""
        if (url.scheme not in {"http", "https"} or url.username is not None or url.password is not None
                or not any(hostname == suffix or hostname.endswith("." + suffix)
                           for suffix in ("xhscdn.com", "xiaohongshu.com"))
                or url.port not in {None, 80, 443}):
            return ""
        return "https://" + value.split("://", 1)[1]
    except (ValueError, TypeError, AttributeError):
        return ""


def _cover(card: dict) -> str:
    value = card.get("cover") or {}
    return image_url(value.get("urlDefault") or value.get("url") or value.get("urlPre") or "")


async def mcp_search(keyword: str, sort: str, period: str) -> dict:
    result = await call("POST", "/api/v1/feeds/search", {"keyword": keyword.strip(), "filters": {
        "sort_by": sort, "publish_time": period, "note_type": "图文"}})
    feeds = result.get("feeds")
    if not isinstance(feeds, list):
        raise HTTPException(502, "采集服务没有返回搜索列表，请检查登录状态")
    hits, records, seen = [], {}, set()
    for feed in feeds[:40]:
        if not isinstance(feed, dict):
            continue
        card = feed.get("noteCard") or {}
        note_id, token = feed.get("id"), feed.get("xsecToken")
        if (feed.get("modelType") != "note" or not isinstance(note_id, str) or not note_id.isalnum()
                or note_id in seen or not isinstance(token, str) or not token):
            continue
        seen.add(note_id)
        key = secrets.token_urlsafe(20)
        meta = {"id": key, "sourceId": note_id, "title": str(card.get("displayTitle") or "未命名笔记")[:300],
                "author": str((card.get("user") or {}).get("nickname") or "")[:100], "cover": _cover(card),
                "likes": str((card.get("interactInfo") or {}).get("likedCount") or ""),
                "sourceUrl": f"https://www.xiaohongshu.com/explore/{note_id}"}
        hits.append(meta)
        records[key] = {"meta": meta, "token": token, "expires": time.time() + 1800}
    with private_store.LOCK:
        cache = private_store.read_document(SEARCH_FILE)
        cache = {k: v for k, v in cache.items() if isinstance(v, dict) and v.get("expires", 0) > time.time()}
        cache.update(records)
        private_store.write_document(SEARCH_FILE, dict(list(cache.items())[-160:]))
    return {"items": hits, "keyword": keyword, "expiresIn": 1800}


async def mcp_detail(result_id: str) -> dict:
    record = private_store.read_document(SEARCH_FILE).get(result_id)
    if not record or record.get("expires", 0) < time.time():
        raise HTTPException(410, "搜索结果已过期，请重新搜索后采集")
    meta = record["meta"]
    response = await call("POST", "/api/v1/feeds/detail", {"feed_id": meta["sourceId"], "xsec_token": record["token"],
        "load_all_comments": False, "comment_config": {"max_comment_items": 1, "click_more_replies": False}})
    try:
        note = response["data"]["note"]
        if note["noteId"] != meta["sourceId"] or not isinstance(note.get("desc", ""), str):
            raise ValueError()
        images = []
        for index, item in enumerate(note.get("imageList") or []):
            if index >= 30:
                raise HTTPException(422, "此笔记图片过多，请改为手动导入需要整理的文字")
            url = image_url(item.get("urlDefault") or item.get("urlPre") or "")
            images.append({"id": f"image-{index + 1}", "url": url, "status": "pending" if url else "failed",
                           "error": None if url else "图片地址不可用"})
        published = note.get("time")
        published_at = datetime.fromtimestamp(published / 1000, timezone.utc).isoformat() if isinstance(published, (int, float)) and 0 < published < 10**14 else None
        return {"platform": "xiaohongshu", "source_id": meta["sourceId"], "source_url": meta["sourceUrl"],
                "title": str(note.get("title") or meta["title"])[:300], "author": str((note.get("user") or {}).get("nickname") or meta["author"])[:100],
                "raw_body": note.get("desc", "")[:60000], "published_at": published_at, "images": images}
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError, OSError):
        raise HTTPException(502, "笔记详情不完整或与搜索结果不匹配，请重新搜索") from None


async def search(keyword: str, sort: str, period: str, platform: str = "xiaohongshu") -> dict:
    from .sources.service import search as unified_search
    return await unified_search(keyword, sort, period, platform)


async def detail(result_id: str) -> dict:
    from .sources.service import detail as unified_detail, RESULTS_FILE
    # 保留升级前尚在有效期内的 MCP 搜索引用。
    if result_id not in private_store.read_document(RESULTS_FILE):
        return await mcp_detail(result_id)
    return await unified_detail(result_id)
