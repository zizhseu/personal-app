"""待办接口回归测试，使用独立内存库，不访问用户数据。"""
import unittest
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.modules.todo.models import TodoCategory, TodoItem
from app.modules.todo.router import router


class TodoApiTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )

        @event.listens_for(self.engine, "connect")
        def enable_foreign_keys(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        TodoCategory.__table__.create(self.engine)
        TodoItem.__table__.create(self.engine)
        app = FastAPI()
        app.include_router(router)

        def isolated_db():
            with Session(self.engine) as session:
                yield session

        app.dependency_overrides[get_db] = isolated_db
        self.client = TestClient(app)
        self.category = self.client.post("/api/todo/categories", json={"name": "学习"}).json()

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def create_item(self, **values):
        payload = {"categoryId": self.category["id"], "title": "复习 Java", **values}
        response = self.client.post("/api/todo/items", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_crud_preserves_category_and_optional_fields(self):
        item = self.create_item(title="  复习 Java  ", note="第一步\n第二步", dueAt="2026-09-30T23:05:00")
        self.assertEqual(item["title"], "复习 Java")
        self.assertFalse(item["completed"])
        self.assertIsNone(item["completedAt"])
        self.assertEqual(item["dueAt"], "2026-09-30T23:05:00")
        path = f'/api/todo/items/{item["id"]}'
        updated = self.client.put(path, json={"title": "复习完成"}).json()
        self.assertEqual(updated["note"], "第一步\n第二步")
        self.assertEqual(updated["dueAt"], item["dueAt"])
        cleared = self.client.put(path, json={"note": None, "dueAt": None}).json()
        self.assertIsNone(cleared["note"])
        self.assertIsNone(cleared["dueAt"])
        other = self.client.post("/api/todo/categories", json={"name": "生活"}).json()
        self.create_item(categoryId=other["id"])
        listed = self.client.get("/api/todo/items", params={"category_id": self.category["id"]}).json()
        self.assertEqual([row["id"] for row in listed], [item["id"]])
        self.assertEqual(self.client.delete(path).status_code, 200)
        self.assertEqual(len(self.client.get("/api/todo/items").json()), 1)

    def test_completion_timestamp_is_local_idempotent_and_reversible(self):
        item = self.create_item(dueAt=(datetime.now() - timedelta(days=1)).isoformat())
        path = f'/api/todo/items/{item["id"]}'
        before = datetime.now()
        done = self.client.put(path, json={"completed": True}).json()
        self.assertTrue(done["completed"])
        self.assertLessEqual(before, datetime.fromisoformat(done["completedAt"]))
        self.assertLessEqual(datetime.fromisoformat(done["completedAt"]), datetime.now())
        repeated = self.client.put(path, json={"completed": True, "note": "已完成"}).json()
        self.assertEqual(repeated["completedAt"], done["completedAt"])
        reopened = self.client.put(path, json={"completed": False}).json()
        self.assertFalse(reopened["completed"])
        self.assertIsNone(reopened["completedAt"])
        self.assertEqual(reopened["dueAt"], item["dueAt"])
        self.assertIsNotNone(self.client.put(path, json={"completed": True}).json()["completedAt"])

    def test_directory_with_items_cannot_be_deleted_even_when_completed(self):
        item = self.create_item()
        self.client.put(f'/api/todo/items/{item["id"]}', json={"completed": True})
        path = f'/api/todo/categories/{self.category["id"]}'
        self.assertEqual(self.client.delete(path).status_code, 400)
        self.assertEqual(len(self.client.get("/api/todo/items").json()), 1)
        self.client.delete(f'/api/todo/items/{item["id"]}')
        self.assertEqual(self.client.delete(path).status_code, 200)

    def test_invalid_updates_do_not_corrupt_existing_items(self):
        item = self.create_item()
        path = f'/api/todo/items/{item["id"]}'
        for payload in ({"title": "   "}, {"title": None}, {"completed": None},
                        {"title": "x" * 201}, {"dueAt": "bad-date"}, {"completedAt": "2026-01-01"}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.put(path, json=payload).status_code, 422)
        self.assertEqual(self.client.get("/api/todo/items").json()[0]["title"], item["title"])
        self.assertEqual(self.client.post("/api/todo/items", json={"categoryId": 9999, "title": "不存在"}).status_code, 404)
        self.assertEqual(self.client.put("/api/todo/items/9999", json={"completed": True}).status_code, 404)

    def test_timezone_input_normalizes_to_local_time(self):
        source = datetime(2026, 9, 27, 15, 0, tzinfo=timezone.utc)
        item = self.create_item(dueAt=source.isoformat())
        self.assertEqual(item["dueAt"], source.astimezone().replace(tzinfo=None).isoformat())


if __name__ == "__main__":
    unittest.main()
