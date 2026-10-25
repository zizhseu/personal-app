"""现有浏览器采集的适配器，沿用已验证的 MCP 服务连接和数据校验。"""
import hashlib

from fastapi import HTTPException

from .. import collector, launcher
from .contracts import Capabilities, SearchResult


def connection_key():
    url, token = collector.connection()
    return hashlib.sha256((url + "\0" + token).encode()).hexdigest()


class McpProvider:
    id = "xhs-mcp"
    platform = "xiaohongshu"
    label = "浏览器采集（MCP）"
    description = "通过本机独立浏览器搜索和读取图文笔记，支持发布时间与收藏排序。"
    homepage = "https://github.com/xpzouying/xiaohongshu-mcp"
    capabilities = Capabilities(sorts=("综合", "最新", "最多点赞", "最多收藏"),
                                periods=("不限", "一天内", "一周内", "半年内"), connection_settings=True)

    def availability(self):
        return {"installed": launcher.EXECUTABLE.exists()}

    def connection(self):
        url, token = collector.connection()
        return {"url": url, "tokenConfigured": bool(token)}

    def save_connection(self, payload):
        return collector.save_connection(payload)

    async def start(self):
        from ..router import start_collector
        return start_collector()

    def startup_status(self):
        state = launcher.read_status()
        return {"status": state["status"], "message": state["message"]}

    async def login_status(self):
        data = await collector.call("GET", "/api/v1/login/status")
        return {"loggedIn": data.get("is_logged_in") is True}

    async def login_qrcode(self):
        data = await collector.call("GET", "/api/v1/login/qrcode")
        image = data.get("img", "")
        if image and (not isinstance(image, str) or not image.startswith("data:image/png;base64,") or len(image) > 2_000_000):
            raise HTTPException(502, "采集服务返回的登录二维码不兼容")
        return {"loggedIn": data.get("is_logged_in") is True, "image": image, "timeout": str(data.get("timeout", "300"))[:10]}

    async def search(self, keyword, sort, period):
        key = connection_key()
        data = await collector.mcp_search(keyword, sort, period)
        return [SearchResult(meta=item, locator={"resultId": item["id"], "connectionKey": key}) for item in data["items"]]

    async def fetch(self, locator):
        if locator.get("connectionKey") != connection_key():
            raise HTTPException(409, "此搜索结果的采集连接已更改，请重新搜索后采集")
        return await collector.mcp_detail(locator["resultId"])
