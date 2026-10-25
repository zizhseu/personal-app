"""简历面试回归：独立内存库、模拟模型，不使用个人材料或真实模型。"""
import asyncio
from datetime import datetime, timedelta
from io import BytesIO
import json
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from zipfile import ZipFile

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import httpx
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import app as registered_app  # 仅注册模型，不启动真实应用
from app.core.database import get_db
from app.modules.aitools import service
from app.modules.aitools.models import InterviewOperation, InterviewSession
from app.modules.aitools.router import router
from app.modules.qa.models import QaCategory, QaItem
from app.modules.todo.models import TodoCategory, TodoItem
from app.shared.base import Base

RESUME = "候选人 A\n项目：使用 FastAPI 构建本地面试工具，负责接口与数据持久化。"


class ResumeInterviewTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.app = FastAPI()
        self.app.include_router(router)

        def isolated_db():
            with Session(self.engine) as db:
                yield db

        self.app.dependency_overrides[get_db] = isolated_db
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.resume = self.client.post("/api/aitools/resumes", json={"name": "示例简历", "content": RESUME}).json()
        with Session(self.engine) as db:
            db.add_all([QaCategory(name="复盘"), TodoCategory(name="复习")])
            db.commit()

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def new_session(self):
        response = self.client.post("/api/aitools/interviews", json={"resumeId": self.resume["id"], "targetRole": "AI 应用开发"})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def generate(self, session_id, path, reply, **extra):
        with patch.object(service, "llm_chat", new=AsyncMock(return_value=reply)) as model:
            response = self.client.post(f"/api/aitools/interviews/{session_id}/{path}", json={"requestId": str(uuid4()), **extra})
        return response, model

    def answered_session(self):
        row = self.new_session()
        response, _ = self.generate(row["id"], "start", "你在本地面试工具中如何处理请求重试？")
        self.assertEqual(response.status_code, 200, response.text)
        response, _ = self.generate(row["id"], "messages", "你如何验证重复请求不会重复入库？", content="我通过请求标识去重，并将请求状态和结果一起保存。")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def report_for(self, row):
        question, answer = row["messages"][:2]
        return {"summary": "说明了去重思路，需要补充并发验证。", "strengths": ["能说明实现方式"], "improvements": ["补充并发测试依据"], "items": [{
            "questionMessageId": question["id"], "answerMessageId": answer["id"],
            "resumeQuote": "使用 FastAPI 构建本地面试工具", "assessment": "partial", "feedback": "已提到请求标识，但尚未给出并发验证过程。",
            "improvementGuide": "准备一个重复请求的测试，观察记录是否重复。", "knowledgePoints": ["幂等性"],
        }]}

    def completed_session(self):
        row = self.answered_session()
        response, _ = self.generate(row["id"], "review", json.dumps(self.report_for(row), ensure_ascii=False))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_resume_edits_and_deletion_preserve_interview_snapshot(self):
        row = self.new_session()
        self.client.put(f"/api/aitools/resumes/{self.resume['id']}", json={"name": "改过的简历", "content": "另一版内容"})
        self.client.delete(f"/api/aitools/resumes/{self.resume['id']}")
        saved = self.client.get(f"/api/aitools/interviews/{row['id']}").json()
        self.assertEqual(saved["resumeContent"], RESUME)
        self.assertEqual(saved["resumeName"], "示例简历")
        self.assertIsNone(saved["resumeId"])

    def test_interview_uses_resume_and_backend_history(self):
        row = self.new_session()
        response, model = self.generate(row["id"], "start", "你在 FastAPI 项目中负责哪些接口？")
        self.assertEqual(response.status_code, 200, response.text)
        prompt = model.await_args.args[0]
        self.assertIn(RESUME, json.loads(prompt[1]["content"].split("\n", 1)[1])["简历原文"])
        self.assertIn("不照着固定题库", prompt[0]["content"])
        self.assertEqual(response.json()["messages"][0]["role"], "assistant")
        response, model = self.generate(row["id"], "messages", "你如何验证？", content="我负责接口与数据库。")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(model.await_args.args[0][-1]["content"], "我负责接口与数据库。")
        self.assertEqual(len(self.client.get(f"/api/aitools/interviews/{row['id']}").json()["messages"]), 3)

    def test_failed_answer_is_saved_and_retry_does_not_duplicate_it(self):
        row = self.new_session()
        self.generate(row["id"], "start", "请介绍个人职责。")
        request_id = str(uuid4())
        payload = {"requestId": request_id, "content": "我负责接口设计。"}
        with patch.object(service, "llm_chat", new=AsyncMock(side_effect=HTTPException(504, "模型超时"))):
            response = self.client.post(f"/api/aitools/interviews/{row['id']}/messages", json=payload)
        self.assertEqual(response.status_code, 504)
        saved = self.client.get(f"/api/aitools/interviews/{row['id']}").json()
        self.assertEqual([m["role"] for m in saved["messages"]], ["assistant", "user"])
        self.assertEqual(saved["lastOperation"]["status"], "failed")
        with patch.object(service, "llm_chat", new=AsyncMock(return_value="请说明具体技术选择。")) as model:
            response = self.client.post(f"/api/aitools/interviews/{row['id']}/retry", json={"requestId": request_id})
            repeated = self.client.post(f"/api/aitools/interviews/{row['id']}/messages", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(repeated.json()["messages"]), 3)
        self.assertEqual(model.await_count, 1)
        changed = self.client.post(f"/api/aitools/interviews/{row['id']}/messages", json={**payload, "content": "另一段回答"})
        self.assertEqual(changed.status_code, 409)

    def test_invalid_reports_do_not_complete_or_export_the_interview(self):
        row = self.answered_session()
        original = self.report_for(row)
        invalid = [[], {**original, "items": []}]
        for update_item in ({"resumeQuote": "虚构的百万用户指标"}, {"answerMessageId": 9999}, {"questionMessageId": True}):
            invalid.append({**original, "items": [{**original["items"][0], **update_item}]})
        invalid.append({**original, "items": original["items"] * 2})
        for payload in invalid:
            with self.subTest(payload=payload):
                response, _ = self.generate(row["id"], "review", json.dumps(payload))
                self.assertEqual(response.status_code, 502, response.text)
                saved = self.client.get(f"/api/aitools/interviews/{row['id']}").json()
                self.assertEqual(saved["status"], "active")
                self.assertIsNone(saved["report"])
                self.assertEqual(len(saved["messages"]), 3)

    def test_report_covers_every_answered_question(self):
        row = self.answered_session()
        response, _ = self.generate(row["id"], "messages", "还有什么改进？", content="我会并发发送两次同标识的请求。")
        row = response.json()
        missing, _ = self.generate(row["id"], "review", json.dumps(self.report_for(row)))
        self.assertEqual(missing.status_code, 502)

    def test_review_can_retry_and_confirmed_exports_are_idempotent(self):
        row = self.answered_session()
        request_id = str(uuid4())
        with patch.object(service, "llm_chat", new=AsyncMock(return_value="无法解析的报告")):
            self.client.post(f"/api/aitools/interviews/{row['id']}/review", json={"requestId": request_id})
        with patch.object(service, "llm_chat", new=AsyncMock(return_value=json.dumps(self.report_for(row)))):
            response = self.client.post(f"/api/aitools/interviews/{row['id']}/retry", json={"requestId": request_id})
        self.assertEqual(response.status_code, 200, response.text)
        with Session(self.engine) as db:
            self.assertEqual(list(db.scalars(select(QaItem))), [])
            self.assertEqual(list(db.scalars(select(TodoItem))), [])
        for kind in ("qa", "todo"):
            payload = {"itemIndex": 0, "kind": kind, "categoryId": 1, "title": "复习请求幂等性", "content": "补充并发验证过程。"}
            first = self.client.post(f"/api/aitools/interviews/{row['id']}/actions", json=payload)
            second = self.client.post(f"/api/aitools/interviews/{row['id']}/actions", json=payload)
            self.assertEqual(first.status_code, 200, first.text)
            self.assertEqual(first.json(), second.json())
        self.client.delete(f"/api/aitools/interviews/{row['id']}")
        with Session(self.engine) as db:
            self.assertEqual(len(list(db.scalars(select(QaItem)))), 1)
            self.assertEqual(len(list(db.scalars(select(TodoItem)))), 1)

    def test_invalid_export_and_empty_report_do_not_mutate_records(self):
        row = self.new_session()
        response, model = self.generate(row["id"], "review", "不应调用模型")
        self.assertEqual(response.status_code, 422)
        model.assert_not_awaited()
        response = self.client.post(f"/api/aitools/interviews/{row['id']}/actions", json={"itemIndex": 0, "kind": "qa", "categoryId": 1, "title": "未经复盘", "content": ""})
        self.assertEqual(response.status_code, 422)
        with Session(self.engine) as db:
            self.assertEqual(list(db.scalars(select(QaItem))), [])

    def test_deleted_export_can_be_created_again_without_duplicates(self):
        row = self.completed_session()
        for kind, model in (("qa", QaItem), ("todo", TodoItem)):
            payload = {"itemIndex": 0, "kind": kind, "categoryId": 1, "title": "复习幂等性", "content": "验证过程"}
            first = self.client.post(f"/api/aitools/interviews/{row['id']}/actions", json=payload)
            self.assertEqual(first.status_code, 200, first.text)
            with Session(self.engine) as db:
                db.delete(db.get(model, first.json()["targetId"]))
                db.commit()
            recreated = self.client.post(f"/api/aitools/interviews/{row['id']}/actions", json=payload)
            self.assertEqual(recreated.status_code, 200, recreated.text)
            with Session(self.engine) as db:
                self.assertEqual(len(list(db.scalars(select(model)))), 1)

    def test_pending_duplicate_requests_and_expired_attempts_are_safe(self):
        row = self.new_session()

        async def exercise():
            entered, release = asyncio.Event(), asyncio.Event()
            calls = 0

            async def model_reply(_):
                nonlocal calls
                calls += 1
                if calls == 1:
                    entered.set()
                    await release.wait()
                    return "迟到的旧回复"
                return "重试后的有效问题"

            request_id = str(uuid4())
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test", trust_env=False) as client:
                with patch.object(service, "llm_chat", new=AsyncMock(side_effect=model_reply)):
                    old = asyncio.create_task(client.post(f"/api/aitools/interviews/{row['id']}/start", json={"requestId": request_id}))
                    await asyncio.wait_for(entered.wait(), 3)
                    duplicate = await client.post(f"/api/aitools/interviews/{row['id']}/start", json={"requestId": request_id})
                    conflict = await client.post(f"/api/aitools/interviews/{row['id']}/start", json={"requestId": str(uuid4())})
                    self.assertEqual(duplicate.status_code, 200)
                    self.assertEqual(duplicate.json()["lastOperation"]["status"], "pending")
                    self.assertEqual(conflict.status_code, 409)
                    with Session(self.engine) as db:
                        db.get(InterviewOperation, request_id).updated_at = datetime.now() - timedelta(minutes=5)
                        db.commit()
                    expired = (await client.get(f"/api/aitools/interviews/{row['id']}")).json()
                    self.assertEqual(expired["lastOperation"]["status"], "failed")
                    retried = await client.post(f"/api/aitools/interviews/{row['id']}/retry", json={"requestId": request_id})
                    self.assertEqual(retried.status_code, 200, retried.text)
                    release.set()
                    self.assertEqual((await asyncio.wait_for(old, 3)).status_code, 409)
                    saved = (await client.get(f"/api/aitools/interviews/{row['id']}")).json()
                    self.assertEqual([m["content"] for m in saved["messages"]], ["重试后的有效问题"])
        asyncio.run(exercise())

    def test_file_extraction_is_preview_only_and_handles_supported_formats(self):
        xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>项目经历</w:t></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>接口与持久化</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'
        buffer = BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", xml)
        samples = [("简历.md", RESUME.encode()), ("简历.docx", buffer.getvalue())]
        writer = PdfWriter()
        page = writer.add_blank_page(width=600, height=800)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 50 700 Td (Resume: FastAPI project) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
        pdf = BytesIO()
        writer.write(pdf)
        samples.append(("resume.pdf", pdf.getvalue()))
        for filename, data in samples:
            with self.subTest(filename=filename):
                response = self.client.post("/api/aitools/resumes/extract", files={"file": (filename, data)})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertTrue(response.json()["content"])
        self.assertEqual(len(self.client.get("/api/aitools/resumes").json()), 1)

    def test_invalid_or_image_only_documents_have_actionable_errors(self):
        writer = PdfWriter()
        writer.add_blank_page(width=600, height=800)
        pdf = BytesIO()
        writer.write(pdf)
        for filename, data in (("坏文件.pdf", b"not a pdf"), ("空白.pdf", pdf.getvalue()), ("旧格式.doc", b"unknown"), ("错误.docx", b"not zip")):
            with self.subTest(filename=filename):
                response = self.client.post("/api/aitools/resumes/extract", files={"file": (filename, data)})
                self.assertEqual(response.status_code, 422, response.text)
