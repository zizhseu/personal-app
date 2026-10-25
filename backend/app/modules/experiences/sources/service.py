"""统一搜索和获取材料，搜索引用绑定原实现，切换不会串用凭据。"""
import secrets
import time

from fastapi import HTTPException
from pydantic import ValidationError

from app.core import private_store
from . import registry
from .contracts import CollectedMaterial
from .assets import image_url

RESULTS_FILE = "experience-results.private"


async def search(keyword, sort="综合", period="不限", platform="xiaohongshu"):
    selected = registry.provider(platform)
    if sort not in selected.capabilities.sorts or period not in selected.capabilities.periods:
        raise HTTPException(422, "当前采集方式不支持所选筛选条件，请重新选择")
    raw = await selected.search(keyword, sort, period)
    hits, records, seen = [], {}, set()
    for hit in raw[:40]:
        source_id = hit.meta.get("sourceId")
        if not isinstance(source_id, str) or not source_id or len(source_id) > 100 or source_id in seen:
            continue
        seen.add(source_id)
        result_id = secrets.token_urlsafe(20)
        public = {key: str(hit.meta.get(key) or "")[:limit] for key, limit in
                  (("sourceId", 100), ("title", 300), ("author", 100), ("likes", 40), ("sourceUrl", 2000))}
        public.update(id=result_id, platform=platform, providerId=selected.id, cover=image_url(hit.meta.get("cover", ""), platform))
        hits.append(public)
        records[result_id] = {"platform": platform, "provider": selected.id, "locator": hit.locator,
                              "sourceId": source_id, "expires": time.time() + 1800}
    with private_store.LOCK:
        cache = private_store.read_document(RESULTS_FILE)
        cache = {k: v for k, v in cache.items() if isinstance(v, dict) and v.get("expires", 0) > time.time()}
        cache.update(records)
        private_store.write_document(RESULTS_FILE, dict(list(cache.items())[-160:]))
    return {"items": hits, "keyword": keyword, "expiresIn": 1800, "platform": platform, "providerId": selected.id}


async def detail(result_id):
    record = private_store.read_document(RESULTS_FILE).get(result_id)
    if not record or record.get("expires", 0) < time.time():
        raise HTTPException(410, "搜索结果已过期，请重新搜索后采集")
    selected = registry.provider(record["platform"], record["provider"])
    result = await selected.fetch(record["locator"])
    if result.get("platform") != record["platform"] or result.get("source_id") != record["sourceId"]:
        raise HTTPException(502, "采集内容与搜索结果不匹配，请重新搜索")
    try:
        normalized = CollectedMaterial.model_validate(result).model_dump()
    except (ValidationError, ValueError, TypeError):
        raise HTTPException(502, "采集材料格式不完整，请检查来源适配器版本") from None
    for image in normalized["images"]:
        image["url"] = image_url(image["url"], record["platform"])
        image["status"] = "pending" if image["url"] else "failed"
        image["error"] = None if image["url"] else "图片地址不可用"
    return normalized
