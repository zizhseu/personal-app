"""手撕题回归：使用内存库，不接触业务数据或执行保存的代码。"""
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.modules.coding.models import CodingCategory, CodingItem
from app.modules.coding.router import router


class CodingTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        CodingCategory.__table__.create(self.engine)
        CodingItem.__table__.create(self.engine)
        app = FastAPI()
        app.include_router(router)
        def isolated_db():
            with Session(self.engine) as db:
                yield db
        app.dependency_overrides[get_db] = isolated_db
        self.client = TestClient(app)
        self.category = self.client.post('/api/coding/categories', json={"name": " 算法 "}).json()
        self.payload = {"categoryId": self.category["id"], "title": " 手写 LRU 缓存 ", "language": "Python",
            "description": "实现 get、put，容量为 0 时如何处理？", "code": "class LRU:\r\n\tdef get(self, key):\r\n\t\treturn None\r\n",
            "approach": "哈希表与双向链表\n注意更新已有 key 的位置。", "complexity": "时间 O(1)，空间 O(n)",
            "sourceUrl": "https://example.invalid/problems/lru", "tags": [" 缓存 ", "链表", "缓存"], "status": "practicing"}

    def tearDown(self):
        self.client.close()
        self.engine.dispose()

    def create(self):
        response = self.client.post('/api/coding/items', json=self.payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def test_code_and_notes_round_trip_without_losing_indentation(self):
        item = self.create()
        self.assertEqual(item['title'], '手写 LRU 缓存')
        self.assertEqual(item['code'], self.payload['code'])
        self.assertEqual(item['tags'], ['缓存', '链表'])
        path = f"/api/coding/items/{item['id']}"
        self.assertEqual(self.client.get(path).json()['approach'], self.payload['approach'])
        updated = {**self.payload, "code": "def solve():\n    return '<script>not executed</script>'\n", "status": "mastered"}
        saved = self.client.put(path, json=updated)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()['code'], updated['code'])
        self.assertEqual(self.client.get(path).json()['status'], 'mastered')

    def test_categories_are_unique_and_nonempty_category_cannot_be_deleted(self):
        self.assertEqual(self.category['name'], '算法')
        self.assertEqual(self.client.post('/api/coding/categories', json={"name": " 算法 "}).status_code, 409)
        for value in (' ', 'x' * 51):
            self.assertEqual(self.client.post('/api/coding/categories', json={"name": value}).status_code, 422)
        item = self.create()
        path = f"/api/coding/categories/{self.category['id']}"
        self.assertEqual(self.client.delete(path).status_code, 400)
        self.assertEqual(self.client.put(path, json={"name": "数据结构"}).json()['name'], '数据结构')
        self.assertEqual(self.client.delete(f"/api/coding/items/{item['id']}").status_code, 200)
        self.assertEqual(self.client.delete(path).status_code, 200)

    def test_invalid_edits_preserve_the_saved_implementation(self):
        item = self.create()
        path = f"/api/coding/items/{item['id']}"
        for changes in ({"title": " "}, {"language": " "}, {"difficulty": "unknown"}, {"status": "unknown"},
                        {"sourceUrl": "javascript:alert(1)"}, {"sourceUrl": "https://user:secret@example.invalid"},
                        {"tags": ['x' * 41]}, {"code": None}, {"categoryId": None}, {"execute": True}):
            response = self.client.put(path, json={**self.payload, **changes})
            self.assertEqual(response.status_code, 422, response.text)
            self.assertEqual(self.client.get(path).json()['code'], self.payload['code'])
        self.assertEqual(self.client.put(path, json={**self.payload, "categoryId": 999}).status_code, 404)
        self.assertEqual(self.client.get(path).json()['categoryId'], self.category['id'])

    def test_move_filter_and_status_do_not_rewrite_code_or_expose_it_in_list(self):
        item = self.create()
        category = self.client.post('/api/coding/categories', json={"name": "工程实现"}).json()
        path = f"/api/coding/items/{item['id']}"
        response = self.client.put(path, json={**self.payload, "categoryId": category['id']})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/coding/items', params={"category_id": self.category['id']}).json(), [])
        listed = self.client.get('/api/coding/items', params={"category_id": category['id']}).json()
        self.assertEqual([row['id'] for row in listed], [item['id']])
        self.assertNotIn('code', listed[0])
        self.assertNotIn('description', listed[0])
        response = self.client.patch(path + '/status', json={"status": "mastered"})
        self.assertEqual(response.json()['status'], 'mastered')
        self.assertEqual(response.json()['code'], self.payload['code'])

    def test_missing_records_and_invalid_status_have_clear_errors(self):
        for method, path, payload in (
            ('get', '/api/coding/items/999', None), ('delete', '/api/coding/items/999', None),
            ('put', '/api/coding/items/999', self.payload), ('delete', '/api/coding/categories/999', None),
        ):
            kwargs = {"json": payload} if payload is not None else {}
            self.assertEqual(self.client.request(method.upper(), path, **kwargs).status_code, 404)
        item = self.create()
        self.assertEqual(self.client.patch(f"/api/coding/items/{item['id']}/status", json={"status": "bad"}).status_code, 422)
