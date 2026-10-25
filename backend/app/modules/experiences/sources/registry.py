"""显式注册平台与实现；配置只能选择注册项，不能提供可执行命令。"""
from fastapi import HTTPException
from threading import RLock

from app.core import private_store
from .contracts import Platform, SourceProvider

CONFIG_FILE = "experience-sources.private"
_platforms = {"xiaohongshu": Platform("xiaohongshu", "小红书", ("xhscdn.com", "xiaohongshu.com"), "https://www.xiaohongshu.com/")}
_providers: dict[str, SourceProvider] = {}
_loaded = False
_lock = RLock()


def register(platform: Platform, provider: SourceProvider):
    if provider.platform != platform.id or provider.id in _providers:
        raise ValueError("来源平台注册冲突")
    if platform.id in _platforms and _platforms[platform.id] != platform:
        raise ValueError("来源平台下载规则冲突")
    _platforms[platform.id] = platform
    _providers[provider.id] = provider


def _load():
    global _loaded
    with _lock:
        if not _loaded:
            from .mcp import McpProvider
            from .cli import CliProvider
            platform = _platforms["xiaohongshu"]
            register(platform, McpProvider())
            register(platform, CliProvider())
            _loaded = True


def get_platform(platform: str) -> Platform:
    if platform not in _platforms:
        raise ValueError("不支持的来源平台")
    return _platforms[platform]


def provider(platform="xiaohongshu", provider_id=None) -> SourceProvider:
    _load()
    if provider_id is None:
        selected = private_store.read_document(CONFIG_FILE)
        provider_id = selected.get(platform) or next((p.id for p in _providers.values() if p.platform == platform), "")
    result = _providers.get(provider_id)
    if not result or result.platform != platform:
        raise HTTPException(422, "不支持的来源平台或采集方式")
    return result


def catalogue():
    _load()
    return {"platforms": [{"id": value.id, "label": value.label, "activeProvider": provider(value.id).id,
        "providers": [{"id": item.id, "label": item.label, "description": item.description, "homepage": item.homepage,
            "capabilities": item.capabilities.public(), **item.availability()}
            for item in _providers.values() if item.platform == value.id]} for value in _platforms.values()]}


def select_provider(platform, provider_id):
    value = provider(platform, provider_id)
    with private_store.LOCK:
        selected = private_store.read_document(CONFIG_FILE)
        selected[platform] = value.id
        private_store.write_document(CONFIG_FILE, selected)
    return catalogue()
