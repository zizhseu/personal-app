"""Offer 轮次类型、岗位阶段过滤与旧记录兼容，使用独立内存库。"""
from datetime import datetime
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core import database
from app.main import app
from app.modules.jobs import service
from app.modules.jobs.constants import ROUND_TYPE_LABELS, ROUND_TYPE_STATUS
from app.modules.jobs.models import InterviewRound
from app.modules.jobs.schemas import ApplicationCreate, ApplicationUpdate, RoundCreate, RoundUpdate
from app.shared.base import Base


OFFER_TYPES = ('verbal_offer', 'formal_offer', 'tripartite')


class OfferRoundTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False, expire_on_commit=False)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def create(self, status='offer'):
        return service.create_application(self.db, ApplicationCreate(company='Offer 轮次示例', position='岗位 A', status=status))

    def fresh(self, app_id):
        self.db.expire_all()
        return service.get_application(self.db, app_id)

    def snapshot(self):
        return {table: self.db.execute(text(f'SELECT * FROM {table} ORDER BY id')).all()
                for table in ('application', 'interview_round', 'status_history', 'round_result_history')}

    def test_three_types_can_be_created_and_serialize_with_original_times(self):
        row = self.create()
        start = datetime(2026, 11, 9, 15)
        for kind in OFFER_TYPES:
            with self.subTest(kind=kind):
                result = service.create_round(self.db, row.id, RoundCreate(
                    round_type=kind, start_at=start, duration_minutes=60))
                self.assertEqual(result.round_type, kind)
                self.assertEqual(result.result, 'not_started')
                self.assertEqual(result.status_history_id, row.status_history[0].id)
                self.assertEqual(result.to_dict()['startAt'], '2026-11-09T15:00:00')
                self.assertEqual(result.to_dict()['scheduledAt'], '2026-11-09T16:00:00')
        row = self.fresh(row.id)
        self.assertEqual([item.round_type for item in row.rounds], list(OFFER_TYPES))
        self.assertEqual([ROUND_TYPE_LABELS[kind] for kind in OFFER_TYPES], ['口头 Offer', '正式 Offer', '三方'])
        self.assertTrue(all(ROUND_TYPE_STATUS[kind] == 'offer' for kind in OFFER_TYPES))
        self.assertIsNone(row.offer_decision)
        self.assertEqual(len(row.status_history), 1)

    def test_other_current_stages_reject_offer_types_without_writes(self):
        for status in ('screening', 'rescreen', 'interviewing'):
            row = self.create(status)
            for kind in OFFER_TYPES:
                before = self.snapshot()
                with self.subTest(status=status, kind=kind), self.assertRaises(HTTPException) as error:
                    service.create_round(self.db, row.id, RoundCreate(round_type=kind))
                self.assertEqual(error.exception.status_code, 422)
                self.assertEqual(self.snapshot(), before)

    def test_offer_stage_rejects_non_offer_round_types(self):
        row = self.create()
        for kind in ('screening', 'assessment', 'written_test', 'ai', 'first', 'second', 'third', 'hr', 'final', 'other'):
            before = self.snapshot()
            with self.subTest(kind=kind), self.assertRaises(HTTPException) as error:
                service.create_round(self.db, row.id, RoundCreate(round_type=kind))
            self.assertEqual(error.exception.status_code, 422)
            self.assertEqual(self.snapshot(), before)

    def test_historical_offer_uses_its_own_stage_and_keeps_current_position(self):
        row = self.create()
        stage_id = row.status_history[0].id
        service.update_application(self.db, row.id, ApplicationUpdate(position='岗位 B', restart_process=True))
        before = self.fresh(row.id).to_dict()
        current_rounds = [item for item in before['rounds'] if item['positionVersion'] == 2]
        for kind in OFFER_TYPES:
            result = service.create_round(self.db, row.id, RoundCreate(
                round_type=kind, position='岗位 A', position_version=1, expected_position_version=2, result='accepted'))
            self.assertEqual((result.position, result.position_version, result.status_history_id), ('岗位 A', 1, stage_id))
        after = self.fresh(row.id).to_dict()
        self.assertEqual((after['position'], after['status']), ('岗位 B', 'screening'))
        self.assertEqual(after['statusHistory'], before['statusHistory'])
        self.assertEqual([item for item in after['rounds'] if item['positionVersion'] == 2], current_rounds)
        self.assertTrue(all(item['status'] == 'offer' and item['statusHistoryId'] == stage_id for item in after['resultHistory']))

    def test_historical_offer_rejects_interview_round_and_other_stage_rejects_offer_round(self):
        for old_status, kind in (('offer', 'first'), ('offer', 'other'), ('rescreen', 'verbal_offer')):
            row = self.create(old_status)
            service.update_application(self.db, row.id, ApplicationUpdate(position='岗位 B', restart_process=True))
            before = self.snapshot()
            with self.subTest(old_status=old_status, kind=kind), self.assertRaises(HTTPException) as error:
                service.create_round(self.db, row.id, RoundCreate(round_type=kind, position='岗位 A', position_version=1))
            self.assertEqual(error.exception.status_code, 422)
            self.assertEqual(self.snapshot(), before)

    def test_non_offer_historical_round_backfill_keeps_cross_stage_support(self):
        row = self.create('rescreen')
        service.update_application(self.db, row.id, ApplicationUpdate(position='岗位 B', restart_process=True))
        result = service.create_round(self.db, row.id, RoundCreate(round_type='first', position='岗位 A', position_version=1))
        self.assertEqual(result.round_type, 'first')
        self.assertIsNone(result.status_history_id)

    def test_legacy_offer_type_can_be_saved_and_corrected_in_place(self):
        row = self.create()
        legacy = InterviewRound(application_id=row.id, position='岗位 A', position_version=1,
            status_history_id=row.status_history[0].id, round_type='other', result='completed',
            start_at=datetime(2026, 11, 9, 12), review_note='原复盘内容')
        self.db.add(legacy)
        self.db.commit()
        original_id = legacy.id
        service.update_round(self.db, original_id, RoundUpdate(round_type='other', review_note='补充复盘内容'))
        service.update_application(self.db, row.id, ApplicationUpdate(position='岗位 B', restart_process=True))
        for kind in OFFER_TYPES:
            result = service.update_round(self.db, original_id, RoundUpdate(round_type=kind))
            self.assertEqual(result.id, original_id)
            self.assertEqual(result.result, 'completed')
            self.assertEqual(result.start_at, datetime(2026, 11, 9, 12))
            self.assertEqual(result.review_note, '补充复盘内容')
        row = self.fresh(row.id)
        self.assertEqual((row.position, row.status), ('岗位 B', 'screening'))
        self.assertEqual(len([item for item in row.rounds if item.position_version == 1]), 1)

    def test_http_create_and_update_support_new_types(self):
        row = self.create()
        with patch.dict(app.dependency_overrides, {database.get_db: lambda: self.db}):
            client = TestClient(app)
            path = f'/api/jobs/applications/{row.id}/rounds'
            for kind in OFFER_TYPES:
                response = client.post(path, json={'roundType': kind})
                self.assertEqual(response.status_code, 200)
                updated = client.put(f"/api/jobs/rounds/{response.json()['id']}", json={'roundType': 'formal_offer'})
                self.assertEqual(updated.status_code, 200)
            self.assertEqual(client.post(path, json={'roundType': 'first'}).status_code, 422)
            self.assertEqual(client.post(path, json={'roundType': 'unknown_offer'}).status_code, 422)


if __name__ == '__main__':
    unittest.main()
