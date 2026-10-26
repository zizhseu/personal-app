"""岗位变更与历史快照，全部使用独立内存数据库。"""
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import app  # 注册全部模型，不启动正式服务
from app.core import database
from app.modules.jobs import service
from app.modules.jobs.models import Application, InterviewRound, RoundResultHistory, StatusHistory
from app.modules.jobs.schemas import ApplicationCreate, ApplicationUpdate, ApplicationStatusPatch, RoundCreate, RoundUpdate, StatusHistoryPositionInput
from app.shared.base import Base


class PositionHistoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False, expire_on_commit=False)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def create(self, status='screening'):
        return service.create_application(self.db, ApplicationCreate(company='示例银行', position='岗位 A', status=status))

    def fresh(self, app_id):
        self.db.expire_all()
        return service.get_application(self.db, app_id)

    def test_initial_stage_and_round_capture_position(self):
        row = self.create()
        value = row.to_dict()
        self.assertEqual(value['positionVersion'], 1)
        self.assertEqual(value['statusHistory'][0]['position'], '岗位 A')
        self.assertEqual(value['rounds'][0]['position'], '岗位 A')
        self.assertEqual(value['rounds'][0]['statusHistoryId'], value['statusHistory'][0]['id'])

    def test_failed_old_position_survives_reapplication(self):
        row = self.create()
        old_id = row.rounds[0].id
        service.update_round(self.db, old_id, RoundUpdate(result='failed'))
        row = service.update_application(self.db, row.id, ApplicationUpdate(position='岗位 B', restart_process=True))
        row = self.fresh(row.id)
        self.assertEqual((row.position, row.status, row.position_version), ('岗位 B', 'screening', 2))
        old = next(r for r in row.rounds if r.id == old_id)
        current = next(r for r in row.rounds if r.position_version == 2)
        self.assertEqual((old.position, old.result), ('岗位 A', 'failed'))
        self.assertEqual((current.position, current.result), ('岗位 B', 'not_started'))
        self.assertEqual([h.position for h in row.status_history], ['岗位 A', '岗位 B'])
        self.assertTrue(all(h.position == '岗位 A' for h in row.round_result_history))

    def test_same_status_still_records_position_transition(self):
        row = self.create('interviewing')
        row = service.update_application(self.db, row.id, ApplicationUpdate(position='岗位 B'))
        self.assertEqual(row.status, 'interviewing')
        self.assertEqual([(h.status, h.position) for h in row.status_history], [('interviewing', '岗位 A'), ('interviewing', '岗位 B')])

    def test_a_b_a_periods_do_not_reuse_old_round_for_automatic_pass(self):
        row = self.create('interviewing')
        old = service.create_round(self.db, row.id, RoundCreate(round_type='first', result='completed'))
        service.update_application(self.db, row.id, ApplicationUpdate(position='岗位 B'))
        service.update_application(self.db, row.id, ApplicationUpdate(position='岗位 A'))
        service.patch_status(self.db, row.id, ApplicationStatusPatch(status='offer'))
        row = self.fresh(row.id)
        self.assertEqual(row.position_version, 3)
        self.assertEqual(next(r for r in row.rounds if r.id == old.id).result, 'completed')

    def test_past_round_can_be_updated_after_new_position_starts(self):
        row = self.create('interviewing')
        old = service.create_round(self.db, row.id, RoundCreate(round_type='first', result='failed'))
        old_stage = old.status_history_id
        service.update_application(self.db, row.id, ApplicationUpdate(position='岗位 B', restart_process=True))
        service.update_round(self.db, old.id, RoundUpdate(round_type='first', result='passed', review_note='补记旧轮次结果'))
        row = self.fresh(row.id)
        latest = max(row.round_result_history, key=lambda h: h.id)
        self.assertEqual((latest.position, latest.position_version, latest.status_history_id), ('岗位 A', 1, old_stage))
        self.assertEqual((row.position, row.status), ('岗位 B', 'screening'))

    def test_correcting_stage_updates_only_its_linked_snapshots(self):
        row = self.create()
        old_stage = row.status_history[0].id
        service.update_round(self.db, row.rounds[0].id, RoundUpdate(result='failed'))
        service.update_application(self.db, row.id, ApplicationUpdate(position='岗位 B', restart_process=True))
        service.update_status_position(self.db, old_stage, StatusHistoryPositionInput(position='补录旧岗位'))
        row = self.fresh(row.id)
        self.assertEqual(row.position, '岗位 B')
        self.assertEqual(next(r for r in row.rounds if r.status_history_id == old_stage).position, '补录旧岗位')
        self.assertTrue(all(h.position == '补录旧岗位' for h in row.round_result_history))
        self.assertEqual(next(r for r in row.rounds if r.position_version == 2).position, '岗位 B')

    def test_round_position_correction_updates_its_result_history(self):
        row = self.create()
        round_id = row.rounds[0].id
        service.update_round(self.db, round_id, RoundUpdate(result='failed'))
        service.update_round(self.db, round_id, RoundUpdate(position='历史补录岗位'))
        row = self.fresh(row.id)
        self.assertEqual(row.round_result_history[0].position, '历史补录岗位')
        self.assertIsNone(row.rounds[0].status_history_id)
        self.assertIsNone(row.round_result_history[0].status_history_id)
        self.assertEqual(row.position, '岗位 A')

    def test_legacy_unlinked_round_does_not_attach_to_another_position(self):
        row = self.create('interviewing')
        old = service.create_round(self.db, row.id, RoundCreate(round_type='first', result='failed'))
        original_stage = old.status_history_id
        old.status_history_id = None
        # 模拟旧版本直接覆盖当前岗位后，历史处于同一代次的情况。
        row.position = '岗位 B'
        row.status_history.append(StatusHistory(status='interviewing', position='岗位 B', position_version=1))
        self.db.commit()
        service.update_round(self.db, old.id, RoundUpdate(result='passed'))
        result = max(self.fresh(row.id).round_result_history, key=lambda item: item.id)
        self.assertEqual(result.status_history_id, original_stage)
        self.assertEqual(result.position, '岗位 A')

    def test_noop_and_whitespace_do_not_create_position_period(self):
        row = self.create()
        row = service.update_application(self.db, row.id, ApplicationUpdate(position=' 岗位 A ', note='只修改备注'))
        self.assertEqual(row.position_version, 1)
        self.assertEqual(len(row.status_history), 1)

    def test_stale_edit_is_rejected_and_previous_offer_decision_clears(self):
        row = self.create('offer')
        row.offer_decision = 'accepted'
        self.db.commit()
        service.update_application(self.db, row.id, ApplicationUpdate(position='岗位 B', restart_process=True, expected_position_version=1))
        with self.assertRaises(HTTPException) as error:
            service.update_application(self.db, row.id, ApplicationUpdate(position='过期编辑', expected_position_version=1))
        self.assertEqual(error.exception.status_code, 409)
        row = self.fresh(row.id)
        self.assertEqual(row.position, '岗位 B')
        self.assertIsNone(row.offer_decision)

    def test_stage_deletion_preserves_round_and_result_snapshots(self):
        row = self.create()
        stage_id = row.status_history[0].id
        service.update_round(self.db, row.rounds[0].id, RoundUpdate(result='failed'))
        service.delete_status_history(self.db, stage_id)
        row = self.fresh(row.id)
        self.assertEqual(row.rounds[0].position, '岗位 A')
        self.assertIsNone(row.rounds[0].status_history_id)
        self.assertIsNone(row.round_result_history[0].status_history_id)

    def test_application_deletion_cascades_all_position_periods(self):
        row = self.create()
        service.update_round(self.db, row.rounds[0].id, RoundUpdate(result='failed'))
        service.update_application(self.db, row.id, ApplicationUpdate(position='岗位 B', restart_process=True))
        service.delete_application(self.db, row.id)
        for model in (Application, InterviewRound, StatusHistory, RoundResultHistory):
            self.assertEqual(self.db.scalars(select(model)).all(), [])

    def test_status_progression_links_result_to_new_stage(self):
        row = self.create()
        service.patch_status(self.db, row.id, ApplicationStatusPatch(status='rescreen'))
        row = self.fresh(row.id)
        result = row.round_result_history[0]
        self.assertEqual(result.status_history_id, max(row.status_history, key=lambda h: h.id).id)
        self.assertEqual(result.changed_at, row.status_history[-1].changed_at)
        self.assertEqual(result.position, '岗位 A')

    def test_http_camel_case_change_and_input_validation(self):
        with patch.dict(app.dependency_overrides, {database.get_db: lambda: self.db}):
            client = TestClient(app)
            initial = client.post('/api/jobs/applications', json={'company': '示例银行', 'position': '岗位 A'}).json()
            path = f"/api/jobs/applications/{initial['id']}"
            changed = client.put(path, json={'position': '岗位 B', 'restartProcess': True, 'expectedPositionVersion': 1})
            self.assertEqual(changed.status_code, 200)
            value = changed.json()
            self.assertEqual(value['positionVersion'], 2)
            self.assertEqual([h['position'] for h in value['statusHistory']], ['岗位 A', '岗位 B'])
            stage = value['statusHistory'][0]['id']
            self.assertEqual(client.patch(f'/api/jobs/status-history/{stage}/position', json={'position': '补录 A'}).status_code, 200)
            self.assertEqual(client.get(path).json()['rounds'][0]['position'], '补录 A')
            self.assertEqual(client.put(path, json={'position': '过期表单', 'expectedPositionVersion': 1}).status_code, 409)
            self.assertEqual(client.put(path, json={'position': 'x' * 101}).status_code, 422)
            self.assertEqual(client.put(path, json={'restartProcess': True}).status_code, 422)


class PositionMigrationTests(unittest.TestCase):
    def test_legacy_schema_preserves_unknown_positions_and_links_stages_once(self):
        engine = create_engine('sqlite://', poolclass=StaticPool)
        with engine.begin() as conn:
            conn.execute(text('CREATE TABLE application (id INTEGER PRIMARY KEY, company VARCHAR(100), position VARCHAR(100), url VARCHAR(500), apply_date DATE, salary VARCHAR(50), base JSON, status VARCHAR(20), offer_decision VARCHAR(20), note TEXT, created_at DATETIME, updated_at DATETIME)'))
            conn.execute(text('CREATE TABLE status_history (id INTEGER PRIMARY KEY, application_id INTEGER REFERENCES application(id) ON DELETE CASCADE, status VARCHAR(20), changed_at DATETIME, created_at DATETIME, updated_at DATETIME)'))
            conn.execute(text('CREATE TABLE interview_round (id INTEGER PRIMARY KEY, application_id INTEGER REFERENCES application(id) ON DELETE CASCADE, round_type VARCHAR(20), start_at DATETIME, duration_minutes INTEGER, scheduled_at DATETIME, result VARCHAR(20), result_changed_at DATETIME, review_note TEXT, created_at DATETIME, updated_at DATETIME)'))
            conn.execute(text('CREATE TABLE round_result_history (id INTEGER PRIMARY KEY, application_id INTEGER REFERENCES application(id) ON DELETE CASCADE, round_id INTEGER REFERENCES interview_round(id) ON DELETE CASCADE, status VARCHAR(20), from_result VARCHAR(20), to_result VARCHAR(20), changed_at DATETIME, created_at DATETIME, updated_at DATETIME)'))
            conn.execute(text("INSERT INTO application(id, company, position, status, created_at, updated_at) VALUES (1, '示例银行', '当前岗位', 'interviewing', '2026-09-01 09:00:00', '2026-09-02 12:00:00')"))
            conn.execute(text("INSERT INTO status_history(id, application_id, status, changed_at, created_at, updated_at) VALUES (1, 1, 'interviewing', '2026-09-02 10:00:00', '2026-09-02 10:00:00', '2026-09-02 10:00:00')"))
            conn.execute(text("INSERT INTO interview_round(id, application_id, round_type, result, result_changed_at, created_at, updated_at) VALUES (1, 1, 'first', 'failed', '2026-09-02 12:00:00', '2026-09-02 11:00:00', '2026-09-02 12:00:00')"))
            conn.execute(text("INSERT INTO round_result_history(id, application_id, round_id, status, to_result, changed_at, created_at, updated_at) VALUES (1, 1, 1, 'interviewing', 'failed', '2026-09-02 12:00:00', '2026-09-02 12:00:00', '2026-09-02 12:00:00')"))
        with TemporaryDirectory() as directory, patch.object(database, 'engine', engine), patch.object(database, 'DATA_DIR', Path(directory)):
            database.init_db()
            with engine.begin() as conn:
                for table in ('status_history', 'interview_round', 'round_result_history'):
                    self.assertIsNone(conn.scalar(text(f'SELECT position FROM {table} WHERE id=1')))
                self.assertEqual(conn.scalar(text('SELECT status_history_id FROM interview_round WHERE id=1')), 1)
                self.assertEqual(conn.scalar(text('SELECT status_history_id FROM round_result_history WHERE id=1')), 1)
                conn.execute(text("UPDATE status_history SET position='人工补录' WHERE id=1"))
            database.init_db()
            with engine.connect() as conn:
                self.assertEqual(conn.scalar(text('SELECT position FROM status_history WHERE id=1')), '人工补录')
                self.assertEqual(conn.scalar(text('SELECT COUNT(*) FROM status_history')), 1)
                self.assertEqual(conn.execute(text('PRAGMA foreign_key_check')).all(), [])
        engine.dispose()
