"""验证 AI 候选题与实际入库采用一致的校验规则。"""
import json
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.modules.quiz.models import QuizCategory, QuizItem
from app.modules.quiz.router import router
from app.modules.quiz import service


class QuizParsingTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        QuizCategory.__table__.create(self.engine)
        QuizItem.__table__.create(self.engine)
        app = FastAPI()
        app.include_router(router)

        def isolated_database():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_db] = isolated_database
        self.client = TestClient(app, raise_server_exceptions=False)
        self.category_id = self.client.post("/api/quiz/categories", json={"name": "隔离测试"}).json()["id"]

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def parse(self, payload):
        with patch.object(service, "llm_chat", new=AsyncMock(return_value=payload)):
            return self.client.post("/api/quiz/parse", json={"text": "测试题目原文"})

    def test_valid_preview_can_be_saved_without_editing(self):
        payload = {"questions": [{"question": "  2 + 2 等于多少？  ", "options": ["3", "4"], "answer": [1, 1], "qtype": "single", "analysis": "加法"}]}
        response = self.parse("```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```")
        self.assertEqual(response.status_code, 200, response.text)
        question = response.json()["questions"][0]
        self.assertEqual(question["answer"], [1])
        saved = self.client.post("/api/quiz/items", json={**question, "categoryId": self.category_id})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["question"], "2 + 2 等于多少？")

    def test_invalid_envelopes_return_502_instead_of_server_errors(self):
        for body in ([], None, {}, {"questions": None}, {"questions": {}}, {"questions": [None]}):
            with self.subTest(body=body):
                response = self.parse(json.dumps(body))
                self.assertEqual(response.status_code, 502, response.text)

    def test_invalid_candidates_never_reach_preview(self):
        valid = {"question": "测试", "options": ["A", "B"], "answer": [0], "qtype": "single"}
        for patch_data in ({"qtype": "multi"}, {"options": [str(i) for i in range(9)]}, {"question": "  "}, {"answer": [5]}, {"answer": [True]}, {"options": ["A", ""]}):
            with self.subTest(patch_data=patch_data):
                response = self.parse(json.dumps({"questions": [{**valid, **patch_data}]}))
                self.assertEqual(response.status_code, 502, response.text)
        self.assertEqual(self.client.get("/api/quiz/items").json(), [])

    def test_no_questions_has_a_clear_422_result(self):
        self.assertEqual(self.parse('{"questions": []}').status_code, 422)

    def test_invalid_partial_updates_preserve_the_saved_question(self):
        original = self.client.post("/api/quiz/items", json={
            "categoryId": self.category_id, "question": "保存的题目", "options": ["A", "B", "C"],
            "answer": [2], "qtype": "single", "analysis": "可清空解析",
        }).json()
        for updates in ({"options": ["A", "B"]}, {"qtype": "multi"}, {"answer": [True]}, {"question": " "}, {"options": None}, {"categoryId": None}):
            with self.subTest(updates=updates):
                response = self.client.put(f"/api/quiz/items/{original['id']}", json=updates)
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(self.client.get("/api/quiz/items").json()[0], original)
        cleared = self.client.put(f"/api/quiz/items/{original['id']}", json={"analysis": None})
        self.assertEqual(cleared.status_code, 200, cleared.text)
        self.assertIsNone(cleared.json()["analysis"])
