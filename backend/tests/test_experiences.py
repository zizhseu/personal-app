"""面经模块回归：独立数据库、合成内容及模拟采集/模型，不接触业务资料。"""
from copy import deepcopy
from datetime import datetime, timedelta
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import time
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import httpx
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import app as registered_app
from app.core import config, private_store
from app.core.database import get_db
from app.modules.experiences import collector, launcher, ocr, service
from app.modules.experiences.models import ExperienceExport, ExperienceNote
from app.modules.experiences.router import router
from app.modules.qa.models import QaCategory, QaItem
from app.shared.base import Base

BODY = "示例公司 AI应用开发 一面\n1. Redis 如何保证缓存与数据库一致？\n2. RAG 如何评估检索效果？"
REPORT = {"company": "示例公司", "position": "AI应用开发", "round": "一面", "summary": "围绕缓存一致性和检索评估展开。", "questions": [
    {"question": "Redis 如何保证缓存与数据库一致？", "sourceId": "body", "quote": "Redis 如何保证缓存与数据库一致？", "topics": ["缓存一致性"]},
    {"question": "RAG 如何评估检索效果？", "sourceId": "body", "quote": "RAG 如何评估检索效果？", "topics": ["RAG"]}]}


class ExperienceTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="personal-experiences-")
        self.directory_patch = patch.object(config, "DATA_DIR", Path(self.directory.name))
        self.directory_patch.start()
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.app = FastAPI()
        self.app.include_router(router)
        def isolated_db():
            with Session(self.engine) as db:
                yield db
        self.app.dependency_overrides[get_db] = isolated_db
        self.client = TestClient(self.app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000), raise_server_exceptions=False)
        with Session(self.engine) as db:
            category = QaCategory(name="面经问题")
            db.add(category)
            db.commit()
            self.category_id = category.id

    def tearDown(self):
        self.client.close()
        self.engine.dispose()
        self.directory_patch.stop()
        self.directory.cleanup()

    def manual(self, **extra):
        response = self.client.post("/api/experiences/manual", json={"title": "示例公司技术面经", "content": BODY,
            "sourceUrl": "https://www.xiaohongshu.com/explore/example", **extra})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def analyze(self, note_id, report=None, request_id=None):
        with patch.object(service.model_service, "llm_chat", new=AsyncMock(return_value=json.dumps(REPORT if report is None else report, ensure_ascii=False))) as model:
            response = self.client.post(f"/api/experiences/notes/{note_id}/analyze", json={"requestId": request_id or str(uuid4())})
        return response, model

    def test_manual_import_deduplicates_and_preserves_source_separately(self):
        first = self.manual()
        second = self.manual(title="换一个标题")
        self.assertEqual(first["id"], second["id"])
        self.assertTrue(second["alreadySaved"])
        self.assertEqual(first["rawBody"], BODY)
        self.assertEqual(first["sources"][1]["originalText"], BODY)
        self.assertEqual(len(self.client.get("/api/experiences/notes").json()), 1)
        self.assertEqual(self.client.get(f"/api/experiences/notes/{first['id']}").headers["cache-control"], "no-store")

    def test_invalid_manual_link_and_empty_content_do_not_create_records(self):
        for payload in ({"content": " "}, {"sourceUrl": "javascript:alert(1)"}, {"sourceUrl": "https://user:secret@example.invalid"}):
            response = self.client.post("/api/experiences/manual", json={"title": "标题", "content": BODY, **payload})
            self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get("/api/experiences/notes").json(), [])

    def test_material_edits_preserve_original_and_invalidate_old_report(self):
        note = self.manual()
        report = self.analyze(note["id"])[0].json()
        sources = [{"id": source["id"], "text": source["text"]} for source in report["sources"]]
        sources[1]["text"] += "\n补充的校对文字"
        response = self.client.put(f"/api/experiences/notes/{note['id']}/material", json={"revision": report["revision"], "sources": sources})
        self.assertEqual(response.status_code, 200)
        edited = response.json()
        self.assertIsNone(edited["report"])
        self.assertEqual(edited["rawBody"], BODY)
        self.assertEqual(edited["sources"][1]["originalText"], BODY)
        stale = self.client.put(f"/api/experiences/notes/{note['id']}/material", json={"revision": report["revision"], "sources": sources})
        self.assertEqual(stale.status_code, 409)

    def test_report_has_valid_quotes_and_request_retry_is_idempotent(self):
        note, request_id = self.manual(), str(uuid4())
        response, model = self.analyze(note["id"], request_id=request_id)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(response.json()["report"]["questions"]), 2)
        prompt = model.call_args.args[0]
        self.assertIn("第三方材料", prompt[0]["content"])
        self.assertIn(BODY, "\n".join(source["text"] for source in json.loads(prompt[1]["content"])))
        duplicate, model = self.analyze(note["id"], request_id=request_id)
        self.assertEqual(duplicate.json()["reportId"], response.json()["reportId"])
        model.assert_not_awaited()

    def test_invalid_ai_quotes_metadata_and_structure_do_not_replace_saved_report(self):
        note = self.manual()
        original = self.analyze(note["id"])[0].json()
        cases = []
        for changes in ({"quote": "虚构的问题"}, {"sourceId": "image-99"}, {"quote": "如何保证\n缓存一致"}):
            payload = deepcopy(REPORT)
            payload["questions"][0].update(changes)
            cases.append(payload)
        cases += [{**REPORT, "company": "不存在的公司"}, {"questions": []}, []]
        for payload in cases:
            response, _ = self.analyze(note["id"], report=payload)
            self.assertEqual(response.status_code, 502, response.text)
            current = self.client.get(f"/api/experiences/notes/{note['id']}").json()
            self.assertEqual(current["reportId"], original["reportId"])
            self.assertEqual(current["rawBody"], BODY)

    def test_ai_failure_is_persisted_and_retriable(self):
        note = self.manual()
        with patch.object(service.model_service, "llm_chat", new=AsyncMock(side_effect=HTTPException(504, "模拟超时"))):
            response = self.client.post(f"/api/experiences/notes/{note['id']}/analyze", json={"requestId": str(uuid4())})
        self.assertEqual(response.status_code, 504)
        current = self.client.get(f"/api/experiences/notes/{note['id']}").json()
        self.assertEqual(current["workStatus"], "failed")
        self.assertEqual(current["error"], "模拟超时")
        self.assertEqual(self.analyze(note["id"])[0].status_code, 200)

    def test_expired_operations_can_recover_and_late_attempt_cannot_overwrite(self):
        note = self.manual()
        with Session(self.engine) as db:
            old_id = str(uuid4())
            row = service._claim(db, note["id"], old_id, "analyze")
            row.work_started_at = datetime.now() - timedelta(seconds=service.LEASE_SECONDS + 1)
            db.commit()
        current = self.client.get(f"/api/experiences/notes/{note['id']}").json()
        self.assertEqual(current["workStatus"], "failed")
        new = self.analyze(note["id"])[0].json()
        with Session(self.engine) as db, self.assertRaises(HTTPException):
            service._finish(db, note["id"], old_id, 1, {"report": {"summary": "迟到结果"}})
        self.assertEqual(self.client.get(f"/api/experiences/notes/{note['id']}").json()["reportId"], new["reportId"])

    def test_pending_work_prevents_duplicate_generation_edit_and_delete(self):
        note = self.manual()
        with Session(self.engine) as db:
            service._claim(db, note["id"], str(uuid4()), "analyze")
        self.assertEqual(self.analyze(note["id"])[0].status_code, 409)
        response = self.client.put(f"/api/experiences/notes/{note['id']}/material", json={"revision": 1, "sources": [{"id": "body", "text": "覆盖"}]})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.client.delete(f"/api/experiences/notes/{note['id']}").status_code, 409)

    def test_export_requires_current_report_and_does_not_duplicate_or_invent_answer(self):
        note = self.manual()
        report = self.analyze(note["id"])[0].json()
        payload = {"reportId": report["reportId"], "itemIndex": 0, "categoryId": self.category_id, "title": "整理后确认的问题"}
        first = self.client.post(f"/api/experiences/notes/{note['id']}/export", json=payload)
        second = self.client.post(f"/api/experiences/notes/{note['id']}/export", json=payload)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["qaId"], second.json()["qaId"])
        with Session(self.engine) as db:
            rows = list(db.scalars(select(QaItem)))
            self.assertEqual(len(rows), 1)
            self.assertIn("来源面经", rows[0].answer)
            self.assertIn(REPORT["questions"][0]["quote"], rows[0].answer)
        stale = self.client.post(f"/api/experiences/notes/{note['id']}/export", json={**payload, "reportId": str(uuid4())})
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(self.client.delete(f"/api/experiences/notes/{note['id']}").status_code, 200)
        with Session(self.engine) as db:
            self.assertEqual(len(list(db.scalars(select(QaItem)))), 1)

    def test_ocr_saves_material_separately_and_keeps_partial_failure(self):
        note = self.manual()
        with Session(self.engine) as db:
            row = db.get(ExperienceNote, note["id"])
            row.images = [{"id": "image-1", "url": "https://a.xhscdn.com/one.png", "status": "pending", "error": None},
                          {"id": "image-2", "url": "https://a.xhscdn.com/two.png", "status": "pending", "error": None}]
            db.commit()
        with patch.object(ocr, "available", return_value=True), patch.object(ocr, "download", new=AsyncMock(side_effect=[b"fake-image", HTTPException(502, "图片过期")])), patch.object(ocr, "recognize", return_value={"text": "图片中的面试问题", "confidence": 0.95}), patch.object(ocr, "store_image"):
            response = self.client.post(f"/api/experiences/notes/{note['id']}/ocr", json={"requestId": str(uuid4())})
        self.assertEqual(response.status_code, 200, response.text)
        current = response.json()
        self.assertEqual([image["status"] for image in current["images"]], ["done", "failed"])
        self.assertEqual(current["sources"][-1]["originalText"], "图片中的面试问题")
        self.assertEqual(current["rawBody"], BODY)
        self.assertEqual(current["revision"], 2)

    def test_image_hosts_and_paths_are_restricted(self):
        for url in ("http://127.0.0.1/private", "file:///secret", "https://a.xhscdn.com.evil.invalid/x", "https://user:secret@a.xhscdn.com/x", "https://a.xhscdn.com:8080/x"):
            self.assertEqual(collector.image_url(url), "")
        self.assertEqual(collector.image_url("http://a.xhscdn.com/test.png"), "https://a.xhscdn.com/test.png")
        note = self.manual()
        self.assertEqual(self.client.get(f"/api/experiences/notes/{note['id']}/images/-1").status_code, 404)

    def test_failed_images_do_not_block_later_pending_images(self):
        note = self.manual()
        with Session(self.engine) as db:
            row = db.get(ExperienceNote, note["id"])
            row.images = [{"id": f"image-{i + 1}", "url": f"https://a.xhscdn.com/{i}.png",
                           "status": "failed" if i < 6 else "pending"} for i in range(8)]
            db.commit()
        attempted = []
        async def download(note_id, index, url, platform="xiaohongshu"):
            attempted.append(index)
            if index < 6:
                raise HTTPException(502, "图片过期")
            return b"synthetic"
        with patch.object(ocr, "available", return_value=True), patch.object(ocr, "download", side_effect=download), patch.object(ocr, "recognize", return_value={"text": "后续图片文字", "confidence": 0.96}), patch.object(ocr, "store_image"):
            response = self.client.post(f"/api/experiences/notes/{note['id']}/ocr", json={"requestId": str(uuid4())})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(attempted[:2], [6, 7])
        self.assertEqual(len(attempted), 6)
        self.assertEqual([item["status"] for item in response.json()["images"]][-2:], ["done", "done"])

    def test_connection_tokens_are_private_and_not_reused_for_another_address(self):
        response = self.client.put("/api/experiences/connection", json={"url": "http://127.0.0.1:18060", "token": "synthetic-collector-key"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("synthetic-collector-key", response.text)
        read = self.client.get("/api/experiences/connection")
        self.assertNotIn("synthetic-collector-key", read.text)
        self.client.put("/api/experiences/connection", json={"url": "http://127.0.0.1:18061"})
        self.assertEqual(collector.connection()[1], "")
        invalid = self.client.put("/api/experiences/connection", json={"url": "https://remote.invalid"})
        self.assertEqual(invalid.status_code, 400)

    def test_remote_origin_cannot_read_local_notes(self):
        response = self.client.get("/api/experiences/notes", headers={"Origin": "https://evil.invalid"})
        self.assertEqual(response.status_code, 403)


class CollectorContractTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="experience-search-")
        self.patch = patch.object(config, "DATA_DIR", Path(self.directory.name))
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.directory.cleanup()

    async def test_search_hides_access_tokens_and_collect_uses_only_selected_result(self):
        feed = {"modelType": "note", "id": "abc123", "xsecToken": "synthetic-note-access-token", "noteCard": {
            "displayTitle": "示例面经", "user": {"nickname": "示例作者"}, "cover": {"urlDefault": "https://a.xhscdn.com/cover.png"}}}
        with patch.object(collector, "call", new=AsyncMock(return_value={"feeds": [feed, feed, {"modelType": "hot_query"}]})):
            result = await collector.search("AI 面经", "综合", "不限")
        self.assertEqual(len(result["items"]), 1)
        self.assertNotIn("synthetic-note-access-token", json.dumps(result))
        note = {"noteId": "abc123", "title": "示例面经", "desc": BODY, "imageList": []}
        with patch.object(collector, "call", new=AsyncMock(return_value={"data": {"note": note}})) as call:
            collected = await collector.detail(result["items"][0]["id"])
        self.assertEqual(collected["raw_body"], BODY)
        self.assertEqual(call.call_args.args[2]["xsec_token"], "synthetic-note-access-token")
        self.assertFalse(call.call_args.args[2]["load_all_comments"])
        self.assertNotIn("comments", collected)

    async def test_expired_result_is_not_fetched_and_wrong_note_id_is_rejected(self):
        private_store.write_document(collector.SEARCH_FILE, {"expired": {"expires": time.time() - 1},
            "fresh": {"expires": time.time() + 60, "meta": {"sourceId": "abc123", "sourceUrl": "https://www.xiaohongshu.com/explore/abc123"}, "token": "synthetic"}})
        with patch.object(collector, "call", new=AsyncMock(return_value={"data": {"note": {"noteId": "wrong-id"}}})) as call:
            with self.assertRaises(HTTPException) as caught:
                await collector.detail("expired")
            self.assertEqual(caught.exception.status_code, 410)
            call.assert_not_awaited()
            with self.assertRaises(HTTPException) as caught:
                await collector.detail("fresh")
            self.assertEqual(caught.exception.status_code, 502)

    async def test_retry_fetches_current_image_instead_of_leftover_deleted_note_cache(self):
        path = ocr.image_path(7, 0)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"leftover-old-image")
        original_client = httpx.AsyncClient
        transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"current-note-image"))
        with patch.object(ocr.httpx, "AsyncClient", side_effect=lambda **kwargs: original_client(transport=transport, **kwargs)):
            data = await ocr.download(7, 0, "https://a.xhscdn.com/current.png")
        self.assertEqual(data, b"current-note-image")


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="experience-launcher-")
        self.root = Path(self.directory.name)
        for name, value in (("RUNTIME", self.root), ("STATUS_FILE", self.root / "startup.json"), ("EXECUTABLE", self.root / "collector.exe")):
            mock = patch.object(launcher, name, value)
            mock.start()
            self.addCleanup(mock.stop)
        mock = patch.object(config, "DATA_DIR", self.root / "data")
        mock.start()
        self.addCleanup(mock.stop)
        self.addCleanup(self.directory.cleanup)

    def test_interrupted_installer_is_retriable_instead_of_permanently_starting(self):
        launcher.STATUS_FILE.write_text(json.dumps({"status": "starting", "message": "下载中", "workerPid": 99,
            "updatedAt": time.time() - 20}), encoding="utf-8")
        with patch.object(launcher, "_process_path", return_value=None):
            self.assertEqual(launcher.read_status()["status"], "failed")

    def test_stopped_owned_service_does_not_remain_ready(self):
        launcher.write_status("ready", "已启动", pid=99)
        with patch.object(launcher, "_owned_pid", return_value=False):
            self.assertEqual(launcher.read_status()["status"], "failed")

    @unittest.skipUnless(sys.platform == "win32", "一键启动仅用于 Windows")
    def test_reusing_healthy_service_preserves_verified_pid(self):
        launcher.write_status("ready", "已启动", pid=99)
        with patch.object(launcher, "_owned_pid", return_value=True), patch.object(httpx, "Client") as client:
            client.return_value.__enter__.return_value.get.return_value = httpx.Response(200, json={"data": {"service": "xiaohongshu-mcp"}})
            launcher.start()
            self.assertEqual(launcher.read_status()["pid"], 99)

    def test_browser_cache_and_credentials_are_isolated_for_child_only(self):
        import os
        previous = {key: os.environ.get(key) for key in ("AUTH_TOKEN", "LOCALAPPDATA", "TEMP", "TMP")}
        result = launcher.child_environment("synthetic-token")
        self.assertEqual(result["AUTH_TOKEN"], "synthetic-token")
        self.assertEqual(Path(result["LOCALAPPDATA"]), self.root / "cache")
        self.assertEqual(Path(result["COOKIES_PATH"]), config.DATA_DIR / "xhs" / "cookies.json")
        self.assertEqual(previous, {key: os.environ.get(key) for key in previous})
