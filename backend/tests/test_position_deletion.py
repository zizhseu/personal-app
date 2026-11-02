"""岗位删除范围、空当前岗位与旧请求隔离，全部使用独立内存数据库。"""
from datetime import datetime
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core import database
from app.modules.jobs import service
from app.modules.jobs.models import Application, InterviewRound, RoundResultHistory, StatusHistory, ScheduleEvent
from app.modules.jobs.positions import position_groups
from app.modules.jobs.schemas import ApplicationCreate, ApplicationUpdate, ApplicationStatusPatch, EventCreate, PositionDeleteInput, RoundCreate
from app.shared.base import Base


class PositionDeletionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False, expire_on_commit=False)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def fresh(self, app_id):
        self.db.expire_all()
        return service.get_application(self.db, app_id)

    def periods(self):
        row = service.create_application(self.db, ApplicationCreate(company='岗位删除示例', position='岗位 A', status='interviewing', note='公司备注'))
        service.create_round(self.db, row.id, RoundCreate(round_type='first', result='failed', review_note='第一次岗位 A'))
        service.update_application(self.db, row.id, ApplicationUpdate(position='岗位 B', restart_process=True))
        service.patch_status(self.db, row.id, ApplicationStatusPatch(status='rescreen'))
        service.create_round(self.db, row.id, RoundCreate(round_type='written_test', result='failed'))
        service.update_application(self.db, row.id, ApplicationUpdate(position='岗位 A', restart_process=True))
        return self.fresh(row.id)

    def remove(self, row, position, version):
        return service.delete_position(self.db, row.id, PositionDeleteInput(position=position, position_version=version,
            expected_position_version=row.position_version))

    def test_delete_old_period_preserves_current_and_same_name_reapplication(self):
        row = self.periods()
        before = row.to_dict()
        row = self.remove(row, '岗位 A', 1)
        value = row.to_dict()
        self.assertEqual((row.position, row.position_version, row.status), ('岗位 A', 3, 'screening'))
        for field in ('rounds', 'statusHistory', 'resultHistory'):
            self.assertEqual(value[field], [item for item in before[field] if item['positionVersion'] != 1])
        self.assertEqual(self.db.execute(text('PRAGMA foreign_key_check')).all(), [])

    def test_delete_current_leaves_company_and_other_history_with_no_placeholder(self):
        row = self.periods()
        event = service.create_event(self.db, EventCreate(title='公司宣讲', event_time=datetime(2026, 11, 3), application_id=row.id))
        before = row.to_dict()
        row = self.remove(row, '岗位 A', 3)
        self.assertEqual((row.company, row.note), ('岗位删除示例', '公司备注'))
        self.assertIsNone(row.position)
        self.assertGreater(row.position_version, 3)
        self.assertFalse(row.has_current_position)
        self.assertFalse(row.to_dict()['hasCurrentPosition'])
        self.assertTrue(all(version != row.position_version for version, _ in position_groups(row)))
        for field in ('rounds', 'statusHistory', 'resultHistory'):
            self.assertEqual(row.to_dict()[field], [item for item in before[field] if item['positionVersion'] != 3])
        self.assertEqual(self.db.get(ScheduleEvent, event.id).application_id, row.id)

    def test_last_position_deletion_retains_empty_company_and_can_add_new_position(self):
        row = service.create_application(self.db, ApplicationCreate(company='仅一个岗位', position='岗位 A'))
        row = self.remove(row, '岗位 A', 1)
        self.assertIsNotNone(self.db.get(Application, row.id))
        self.assertEqual(position_groups(row), {})
        for model in (InterviewRound, StatusHistory, RoundResultHistory):
            self.assertEqual(self.db.scalars(select(model)).all(), [])
        empty_version = row.position_version
        row = service.update_application(self.db, row.id, ApplicationUpdate(position='岗位 C', restart_process=True, expected_position_version=empty_version))
        self.assertTrue(row.has_current_position)
        self.assertGreater(row.position_version, empty_version)
        self.assertEqual(row.rounds[0].position, '岗位 C')

    def test_deleted_current_cannot_be_recreated_by_old_round_or_status_requests(self):
        row = self.periods()
        app_id = row.id
        row = self.remove(row, '岗位 A', 3)
        for operation in (
            lambda: service.create_round(self.db, app_id, RoundCreate(round_type='screening')),
            lambda: service.patch_status(self.db, app_id, ApplicationStatusPatch(status='rescreen')),
            lambda: service.update_application(self.db, app_id, ApplicationUpdate(status='offer')),
            lambda: service.create_round(self.db, app_id, RoundCreate(round_type='screening', position='岗位 A', position_version=3, expected_position_version=3)),
        ):
            with self.assertRaises(HTTPException):
                operation()
        row = self.fresh(app_id)
        self.assertFalse(row.has_current_position)
        service.update_application(self.db, app_id, ApplicationUpdate(note='仍可编辑公司备注'))
        self.assertEqual(self.fresh(app_id).note, '仍可编辑公司备注')

    def test_old_position_still_accepts_round_after_current_is_deleted(self):
        row = self.remove(self.periods(), '岗位 A', 3)
        value = service.create_round(self.db, row.id, RoundCreate(position='岗位 B', position_version=2,
            expected_position_version=row.position_version, round_type='first', result='failed'))
        self.assertEqual((value.position, value.position_version), ('岗位 B', 2))
        self.assertFalse(self.fresh(row.id).has_current_position)

    def test_explicit_stage_links_delete_missing_snapshots_in_the_selected_group(self):
        row = self.periods()
        old_round = next(item for item in row.rounds if item.position_version == 1)
        old_round.position = None
        for result in row.round_result_history:
            if result.round_id == old_round.id:
                result.position = None
        self.db.commit()
        row = self.remove(self.fresh(row.id), '岗位 A', 1)
        self.assertFalse(any(item.position_version == 1 for items in (row.rounds, row.status_history, row.round_result_history) for item in items))

    def test_unknown_group_in_same_version_does_not_delete_known_current_position(self):
        row = service.create_application(self.db, ApplicationCreate(company='旧记录', position=None))
        row.position = '岗位 B'
        self.db.commit()
        current = service.create_round(self.db, row.id, RoundCreate(round_type='screening'))
        row = self.remove(self.fresh(row.id), None, 1)
        self.assertEqual((row.position, row.position_version), ('岗位 B', 1))
        self.assertTrue(row.has_current_position)
        self.assertEqual([item.id for item in row.rounds], [current.id])

    def test_result_only_group_can_be_deleted_without_deleting_its_other_position_round(self):
        row = self.periods()
        result = next(item for item in row.round_result_history if item.position_version == 1)
        round_id = result.round_id
        result.position = '单独补录结果'
        self.db.commit()
        row = self.remove(self.fresh(row.id), '单独补录结果', 1)
        self.assertIsNotNone(self.db.get(InterviewRound, round_id))
        self.assertFalse(any(item.position == '单独补录结果' for item in row.round_result_history))

    def test_cross_position_result_cascade_is_rejected_without_deleting_other_records(self):
        row = self.periods()
        result = next(item for item in row.round_result_history if item.position_version == 1)
        result.position = '另一个岗位'
        self.db.commit()
        before = self.fresh(row.id).to_dict()
        with self.assertRaises(HTTPException) as error:
            self.remove(row, '岗位 A', 1)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.fresh(row.id).to_dict(), before)

    def test_cross_company_stage_reference_is_rejected_without_writes(self):
        row = service.create_application(self.db, ApplicationCreate(company='第一家公司', position='岗位 A', status='interviewing'))
        other = service.create_application(self.db, ApplicationCreate(company='第二家公司', position='岗位 Z'))
        other.rounds[0].status_history_id = row.status_history[0].id
        self.db.commit()
        before = self.fresh(row.id).to_dict()
        with self.assertRaises(HTTPException) as error:
            self.remove(row, '岗位 A', 1)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.fresh(row.id).to_dict(), before)
        self.assertEqual(self.fresh(other.id).rounds[0].status_history_id, row.status_history[0].id)

    def test_invalid_or_stale_deletion_does_not_change_records(self):
        row = self.periods()
        before = row.to_dict()
        for payload in [dict(position='不存在', position_version=1, expected_position_version=3),
                        dict(position='岗位 A', position_version=3, expected_position_version=1)]:
            with self.subTest(payload=payload), self.assertRaises(HTTPException) as error:
                service.delete_position(self.db, row.id, PositionDeleteInput(**payload))
            self.assertEqual(error.exception.status_code, 409)
            self.assertEqual(self.fresh(row.id).to_dict(), before)

    def test_http_position_deletion_and_required_confirmation_context(self):
        row = self.periods()
        with patch.dict(app.dependency_overrides, {database.get_db: lambda: self.db}):
            client = TestClient(app)
            path = f'/api/jobs/applications/{row.id}/positions'
            for payload in [{'positionVersion':1}, {'position':'岗位 A','positionVersion':0,'expectedPositionVersion':3},
                            {'position':'岗位 A','positionVersion':1,'expectedPositionVersion':3,'applicationId':999}]:
                self.assertEqual(client.request('DELETE', path, json=payload).status_code, 422)
            response = client.request('DELETE', path, json={'position':'岗位 A','positionVersion':1,'expectedPositionVersion':3})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['hasCurrentPosition'])
            response = client.request('DELETE', path, json={'position':'岗位 A','positionVersion':3,'expectedPositionVersion':3})
            self.assertFalse(response.json()['hasCurrentPosition'])
            self.assertEqual(client.get(f'/api/jobs/applications/{row.id}').status_code, 200)
