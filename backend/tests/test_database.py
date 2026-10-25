"""验证新库启动和旧字段迁移，全部使用独立内存数据库。"""
import json
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app.core import database
from app.main import app  # 导入全部模块模型，不启动应用或访问用户数据库
from app.shared.base import Base


class DatabaseInitializationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", poolclass=StaticPool)
        self.directory = TemporaryDirectory(prefix="personal-app-migration-")
        self.engine_patch = patch.object(database, "engine", self.engine)
        self.directory_patch = patch.object(database, "DATA_DIR", Path(self.directory.name))
        self.engine_patch.start()
        self.directory_patch.start()

    def tearDown(self):
        self.directory_patch.stop()
        self.engine_patch.stop()
        self.engine.dispose()
        self.directory.cleanup()

    def test_empty_database_initializes_and_can_initialize_again(self):
        database.init_db()
        database.init_db()
        self.assertIn("todo_item", inspect(self.engine).get_table_names())
        self.assertIn("coding_category", inspect(self.engine).get_table_names())
        self.assertIn("coding_item", inspect(self.engine).get_table_names())
        self.assertNotIn("location", {c["name"] for c in inspect(self.engine).get_columns("application")})
        with self.engine.connect() as connection:
            self.assertEqual(connection.scalar(text("SELECT COUNT(*) FROM qa_category")), 3)
            created_at = connection.scalar(text("SELECT created_at FROM qa_category LIMIT 1"))
            self.assertLess(abs((datetime.now() - datetime.fromisoformat(created_at)).total_seconds()), 5)

    def test_seeding_after_timezone_migration_uses_local_timestamps(self):
        database.init_db()
        with self.engine.begin() as connection:
            connection.execute(text("DELETE FROM qa_category"))
        database.init_db()
        with self.engine.connect() as connection:
            created_at = connection.scalar(text("SELECT created_at FROM qa_category LIMIT 1"))
            self.assertLess(abs((datetime.now() - datetime.fromisoformat(created_at)).total_seconds()), 5)

    def test_legacy_question_rebuild_preserves_related_questions(self):
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            connection.execute(text("ALTER TABLE qa_item ADD COLUMN category VARCHAR(20)"))
            connection.execute(text("INSERT INTO qa_category (name, created_at, updated_at) VALUES ('Agent', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"))
            connection.execute(text(
                "INSERT INTO qa_item (category, category_id, question, status, related_ids, created_at, updated_at) "
                "VALUES ('agent', 1, '历史问题', 'learning', '[2]', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ))
        database.init_db()
        with self.engine.connect() as connection:
            self.assertEqual(json.loads(connection.scalar(text("SELECT related_ids FROM qa_item"))), [2])
        self.assertNotIn("category", {column["name"] for column in inspect(self.engine).get_columns("qa_item")})

    def test_legacy_location_is_migrated_without_overwriting_existing_base(self):
        Base.metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            connection.execute(text("ALTER TABLE application ADD COLUMN location VARCHAR(200)"))
            connection.execute(text(
                "INSERT INTO application (company, status, location, base, created_at, updated_at) "
                "VALUES ('旧记录', 'applied', '南京 / 上海', NULL, '2026-09-01 00:00:00', '2026-09-01 00:00:00'), "
                "('已调整记录', 'screening', '北京', '[\"深圳\"]', '2026-09-01 00:00:00', '2026-09-01 00:00:00')"
            ))
        database.init_db()
        with self.engine.connect() as connection:
            first = connection.execute(text("SELECT company, status, base, created_at FROM application ORDER BY id")).all()
        database.init_db()
        with self.engine.connect() as connection:
            repeated = connection.execute(text("SELECT company, status, base, created_at FROM application ORDER BY id")).all()
            self.assertEqual(connection.scalar(text("SELECT COUNT(*) FROM status_history")), 2)
        self.assertEqual(first, repeated)
        self.assertEqual(first[0].status, "screening")
        self.assertEqual(json.loads(first[0].base), ["南京", "上海"])
        self.assertEqual(json.loads(first[1].base), ["深圳"])
