"""统一采集契约：独立私有目录、合成材料，不读取真实 Cookie 或调用平台。"""
import json
import importlib
import os
import sys
from types import ModuleType
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core import config, private_store
from app.core.database import get_db
from app.modules.experiences.router import router
from app.modules.experiences import collector, service as material_service
from app.modules.experiences.models import ExperienceNote
from app.modules.experiences.sources import registry, service, cli
from app.modules.experiences.sources.assets import image_url
from app.modules.experiences.sources.contracts import Platform, Capabilities, SearchResult
from app.shared.base import Base

FEED = {"modelType": "note", "id": "abc123", "xsecToken": "private-mcp-token", "noteCard": {"displayTitle": "面经", "user": {"nickname": "作者"}}}
CLI_FEED = {"id": "abc123", "xsec_token": "private-cli-token", "note_card": {"display_title": "面经", "type": "normal", "user": {"nickname": "作者"}, "cover": {"url_default": "https://a.xhscdn.com/cover.png"}}}


class SourceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="source-contract-")
        self.directory_patch = patch.object(config, "DATA_DIR", Path(self.directory.name))
        self.directory_patch.start()
        registry.provider()

    def tearDown(self):
        self.directory_patch.stop()
        self.directory.cleanup()

    async def test_worker_uses_fixed_argv_and_stdin_without_async_subprocess_support(self):
        process = MagicMock()
        process.communicate.return_value = (b'{"ok":true,"data":{"loggedIn":false}}', b'')
        process.poll.return_value = 0
        with patch.object(cli.subprocess, "Popen", return_value=process) as start, patch.object(cli.asyncio, "create_subprocess_exec", side_effect=NotImplementedError):
            result = await cli.execute("detail", id="abc123", token="private-access-token")
        self.assertFalse(result["loggedIn"])
        self.assertNotIn("private-access-token", str(start.call_args.args))
        self.assertEqual(start.call_args.args[0][1:3], ["-m", "app.modules.experiences.sources.cli_worker"])
        self.assertIn(b"private-access-token", process.communicate.call_args.args[0])
        process.terminate.assert_not_called()

    def worker_fixture(self, *, guest=False, failure=None):
        with patch.dict(os.environ, {"PERSONAL_APP_SOURCE_DATA": str(config.DATA_DIR)}):
            worker = importlib.import_module("app.modules.experiences.sources.cli_worker")
        client_type = MagicMock()
        client = client_type.return_value.__enter__.return_value
        client.cookies = {"a1": "cached-device", "web_session": "rotated-session"}
        if failure:
            client.get_self_info.side_effect = failure
        else:
            client.get_self_info.return_value = {"id": "user-1", "guest": guest, "nickname": "Unknown" if guest else "用户"}
        normalizers = ModuleType("xhs_cli.command_normalizers")
        normalizers.normalize_xhs_user_payload = lambda value: value
        exceptions = ModuleType("xhs_cli.exceptions")
        exceptions.SessionExpiredError = type("SessionExpiredError", (Exception,), {})
        modules = {"xhs_cli": ModuleType("xhs_cli"), "xhs_cli.command_normalizers": normalizers, "xhs_cli.exceptions": exceptions}
        return worker, client_type, modules

    async def test_login_status_persists_server_rotated_cookies(self):
        worker, client_type, modules = self.worker_fixture()
        private_store.write_document(cli.COOKIE_FILE, {"a1": "cached-device", "web_session": "previous-session"})
        with patch.object(worker, "load_sdk", return_value=client_type), patch.dict(sys.modules, modules):
            self.assertTrue(worker.dispatch({"op": "status"})["loggedIn"])
        self.assertEqual(private_store.read_document(cli.COOKIE_FILE)["web_session"], "rotated-session")

    async def test_guest_or_network_failure_does_not_replace_cached_login(self):
        previous = {"a1": "cached-device", "web_session": "previous-session"}
        for failure in (None, RuntimeError("temporary network error")):
            worker, client_type, modules = self.worker_fixture(guest=True, failure=failure)
            private_store.write_document(cli.COOKIE_FILE, previous)
            with patch.object(worker, "load_sdk", return_value=client_type), patch.dict(sys.modules, modules):
                if failure:
                    with self.assertRaises(RuntimeError):
                        worker.dispatch({"op": "status"})
                else:
                    self.assertFalse(worker.dispatch({"op": "status"})["loggedIn"])
            self.assertEqual(private_store.read_document(cli.COOKIE_FILE), previous)

    async def test_selection_persists_without_merging_provider_credentials(self):
        collector.save_connection({"url": "http://127.0.0.1:18060", "token": "private-mcp-secret"})
        private_store.write_document(cli.COOKIE_FILE, {"a1": "private-cli-cookie"})
        self.assertEqual(registry.provider().id, "xhs-mcp")
        data = registry.select_provider("xiaohongshu", "xhs-cli")
        self.assertEqual(registry.provider().id, "xhs-cli")
        public = json.dumps(data)
        self.assertNotIn("private-mcp-secret", public)
        self.assertNotIn("private-cli-cookie", public)
        registry.select_provider("xiaohongshu", "xhs-mcp")
        self.assertEqual(collector.connection()[1], "private-mcp-secret")
        self.assertEqual(private_store.read_document(cli.COOKIE_FILE)["a1"], "private-cli-cookie")

    async def test_unsupported_platform_provider_and_filters_are_rejected(self):
        for args in (("bilibili", None), ("xiaohongshu", "arbitrary-command")):
            with self.assertRaises(HTTPException):
                registry.provider(*args)
        registry.select_provider("xiaohongshu", "xhs-cli")
        with patch.object(cli, "execute", new=AsyncMock()) as execute:
            with self.assertRaises(HTTPException) as caught:
                await service.search("面经", "综合", "一周内")
            self.assertEqual(caught.exception.status_code, 422)
            execute.assert_not_awaited()

    async def test_switch_after_search_still_fetches_with_original_provider(self):
        with patch.object(collector, "call", new=AsyncMock(return_value={"feeds": [FEED]})):
            result = await service.search("面经")
        registry.select_provider("xiaohongshu", "xhs-cli")
        with patch.object(collector, "call", new=AsyncMock(return_value={"data": {"note": {"noteId": "abc123", "desc": "原始正文", "imageList": []}}})), patch.object(cli, "execute", new=AsyncMock()) as execute:
            note = await service.detail(result["items"][0]["id"])
        self.assertEqual(note["raw_body"], "原始正文")
        execute.assert_not_awaited()
        self.assertEqual(result["providerId"], "xhs-mcp")
        self.assertNotIn("private-mcp-token", json.dumps(result))

    async def test_changed_connection_cannot_reuse_old_search_locator(self):
        with patch.object(collector, "call", new=AsyncMock(return_value={"feeds": [FEED]})):
            result = await service.search("面经")
        collector.save_connection({"url": "http://127.0.0.1:19060"})
        with self.assertRaises(HTTPException) as caught:
            await service.detail(result["items"][0]["id"])
        self.assertEqual(caught.exception.status_code, 409)

    async def test_cli_normalizes_search_and_hides_tokens(self):
        registry.select_provider("xiaohongshu", "xhs-cli")
        with patch.object(cli, "execute", new=AsyncMock(return_value={"items": [CLI_FEED, CLI_FEED, {"note_card": "invalid"}]})) as execute:
            result = await service.search("AI 面经", "热度")
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["platform"], "xiaohongshu")
        self.assertEqual(result["items"][0]["title"], "面经")
        self.assertNotIn("private-cli-token", json.dumps(result))
        self.assertEqual(execute.call_args.kwargs["sort"], "popularity_descending")

    async def test_cli_normalizes_feed_and_html_and_rejects_wrong_note(self):
        provider = registry.provider("xiaohongshu", "xhs-cli")
        card = {"note_id": "abc123", "title": "题目", "desc": "正文", "image_list": [{"url_default": "https://a.xhscdn.com/image.png"}, {"url_default": "http://127.0.0.1/private"}]}
        for response in ({"items": [{"note_card": card}]}, {"noteId": "abc123", "desc": "正文", "imageList": card["image_list"]}):
            with patch.object(cli, "execute", new=AsyncMock(return_value=response)):
                material = await provider.fetch({"id": "abc123", "token": "secret"})
            self.assertEqual(material["raw_body"], "正文")
            self.assertEqual(material["images"][0]["status"], "pending")
            self.assertEqual(material["images"][1]["status"], "failed")
        with patch.object(cli, "execute", new=AsyncMock(return_value={"noteId": "different"})):
            with self.assertRaises(HTTPException):
                await provider.fetch({"id": "abc123", "token": "secret"})

    async def test_cli_locator_is_bound_to_login_session(self):
        private_store.write_document("experience-cli-session.private", {"id": "new-account"})
        with patch.object(cli, "execute", new=AsyncMock()) as execute:
            with self.assertRaises(HTTPException) as caught:
                await registry.provider("xiaohongshu", "xhs-cli").fetch({"id": "abc123", "token": "secret", "session": "old-account"})
        self.assertEqual(caught.exception.status_code, 409)
        execute.assert_not_awaited()

    async def test_same_platform_content_is_deduplicated_across_providers(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            payload = {"platform": "xiaohongshu", "source_id": "abc123", "source_url": "https://www.xiaohongshu.com/explore/abc123", "title": "原题", "author": "作者", "raw_body": "正文", "images": []}
            first = material_service._save_note(db, payload)
            second = material_service._save_note(db, {**payload, "title": "另一采集器的标题"})
            self.assertEqual(first["id"], second["id"])
            self.assertEqual(len(list(db.scalars(select(ExperienceNote)))), 1)
            self.assertEqual(second["title"], "原题")
        engine.dispose()

    async def test_new_platform_uses_same_search_contract_and_own_image_policy(self):
        class FixtureProvider:
            id, platform, label, description, homepage = "fixture-api", "fixture", "测试来源", "合成资料", "https://fixture.invalid"
            capabilities = Capabilities()
            def availability(self): return {"installed": True}
            async def search(self, keyword, sort, period):
                return [SearchResult({"sourceId": "same-id", "title": "跨平台资料", "sourceUrl": "https://fixture.invalid/item"}, {"id": "same-id"})]
            async def fetch(self, locator):
                return {"platform": self.platform, "source_id": locator["id"], "raw_body": "正文"}
        registry.register(Platform("fixture", "测试平台", ("images.fixture.invalid",), "https://fixture.invalid/"), FixtureProvider())
        try:
            result = await service.search("面经", platform="fixture")
            material = await service.detail(result["items"][0]["id"])
            self.assertEqual(material["platform"], "fixture")
            self.assertEqual(image_url("https://images.fixture.invalid/image", "fixture"), "https://images.fixture.invalid/image")
            self.assertEqual(image_url("https://a.xhscdn.com/image", "fixture"), "")
            self.assertEqual(image_url("https://images.fixture.invalid/image", "xiaohongshu"), "")
        finally:
            registry._providers.pop("fixture-api")
            registry._platforms.pop("fixture")


class SourceApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="source-api-")
        self.patch = patch.object(config, "DATA_DIR", Path(self.directory.name))
        self.patch.start()
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        api = FastAPI()
        api.include_router(router)
        def db():
            with Session(self.engine) as session:
                yield session
        api.dependency_overrides[get_db] = db
        self.client = TestClient(api, base_url="http://127.0.0.1", client=("127.0.0.1", 50000))

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        self.patch.stop()
        self.directory.cleanup()

    def test_settings_validation_and_login_states_are_provider_specific(self):
        response = self.client.get("/api/experiences/sources")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["platforms"][0]["providers"]), 2)
        selected = self.client.put("/api/experiences/sources/xiaohongshu", json={"providerId": "xhs-cli"})
        self.assertEqual(selected.json()["platforms"][0]["activeProvider"], "xhs-cli")
        self.assertEqual(self.client.put("/api/experiences/sources/xiaohongshu", json={"providerId": "shell", "command": "ignored"}).status_code, 422)
        with patch.object(collector, "call", new=AsyncMock(return_value={"is_logged_in": True})):
            mcp = self.client.get("/api/experiences/sources/xiaohongshu/xhs-mcp/login")
        other = self.client.get("/api/experiences/sources/xiaohongshu/xhs-cli/login")
        self.assertTrue(mcp.json()["loggedIn"])
        self.assertFalse(other.json()["loggedIn"])
        remote = self.client.get("/api/experiences/sources", headers={"Origin": "https://untrusted.example"})
        self.assertEqual(remote.status_code, 403)

    def test_search_collect_and_deduplicate_across_both_implementations(self):
        with patch.object(collector, "call", new=AsyncMock(return_value={"feeds": [FEED]})):
            hit = self.client.post("/api/experiences/search", json={"keyword": "示例面经"}).json()["items"][0]
        note = {"noteId": "abc123", "title": "面经", "desc": "保留原始正文", "imageList": []}
        with patch.object(collector, "call", new=AsyncMock(return_value={"data": {"note": note}})):
            first = self.client.post("/api/experiences/collect", json={"resultId": hit["id"]})
        self.assertEqual(first.status_code, 200)
        self.client.put("/api/experiences/sources/xiaohongshu", json={"providerId": "xhs-cli"})
        with patch.object(cli, "execute", new=AsyncMock(return_value={"items": [CLI_FEED]})):
            second_hit = self.client.post("/api/experiences/search", json={"keyword": "示例面经", "platform": "xiaohongshu"}).json()["items"][0]
        with patch.object(cli, "execute", new=AsyncMock(return_value=note)):
            second = self.client.post("/api/experiences/collect", json={"resultId": second_hit["id"]})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(len(self.client.get("/api/experiences/notes").json()), 1)
