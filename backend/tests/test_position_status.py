"""验证各岗位的状态、轮次联动和并发校验彼此独立。"""
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
from app.modules.jobs.positions import position_groups, position_summaries
from app.modules.jobs.schemas import (
    ApplicationCreate, ApplicationStatusPatch, ApplicationUpdate, PositionDeleteInput,
    PositionStatusPatch, PrimaryPositionInput, RoundCreate, RoundUpdate,
)
from app.shared.base import Base


class PositionStatusTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False, expire_on_commit=False)
        row = service.create_application(self.db, ApplicationCreate(company='独立状态示例', position='研发岗位', status='rescreen'))
        service.create_round(self.db, row.id, RoundCreate(round_type='written_test', result='completed'))
        row = service.update_application(self.db, row.id, ApplicationUpdate(position='研究岗位', restart_process=True))
        row = self.fresh(row.id)
        initial = next(item for item in row.rounds if item.position_version == 2)
        service.update_round(self.db, initial.id, RoundUpdate(position='Coding 岗位', result='passed'))
        service.patch_status(self.db, row.id, ApplicationStatusPatch(status='rescreen'))
        service.create_round(self.db, row.id, RoundCreate(position='Coding 岗位', position_version=2, round_type='written_test', result='completed'))
        service.create_round(self.db, row.id, RoundCreate(round_type='assessment', result='completed'))
        row = self.fresh(row.id)
        service.set_primary_position(self.db, row.id, PrimaryPositionInput(
            position='研究岗位', position_version=2, expected_position_version=2))
        self.app_id = row.id

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def fresh(self, app_id=None):
        self.db.expire_all()
        return service.get_application(self.db, app_id or self.app_id)

    def summary(self, position, version, row=None):
        return next(item for item in position_summaries(row or self.fresh())
                    if item['position'] == position and item['positionVersion'] == version)

    def request(self, position, version, status, row=None):
        row = row or self.fresh()
        group = position_groups(row)[(version, position)]
        stage = max(group.stages, key=lambda item: (item.changed_at, item.id), default=None)
        return PositionStatusPatch(
            position=position, position_version=version, expected_position_version=row.position_version,
            status=status, expected_status=self.summary(position, version, row)['status'],
            expected_status_history_id=stage.id if stage else None,
        )

    def change(self, position, version, status):
        return service.patch_position_status(self.db, self.app_id, self.request(position, version, status))

    def application_record(self):
        return self.db.execute(text('SELECT * FROM application WHERE id = :id'), {'id': self.app_id}).one()

    def group_snapshot(self, position, version):
        group = position_groups(self.fresh())[(version, position)]
        return {
            'rounds': [item.to_dict() for item in group.rounds],
            'stages': [item.to_dict() for item in group.stages],
            'results': [item.to_dict() for item in group.results],
        }

    def all_records(self):
        return {table: self.db.execute(text(f'SELECT * FROM {table} ORDER BY id')).all()
                for table in ('application', 'interview_round', 'status_history', 'round_result_history')}

    def test_non_primary_position_changes_its_own_status_and_round_only(self):
        before_application = self.application_record()
        current = self.group_snapshot('研究岗位', 2)
        same_version = self.group_snapshot('Coding 岗位', 2)
        row = self.change('研发岗位', 1, 'interviewing')
        self.assertEqual(self.summary('研发岗位', 1, row)['status'], 'interviewing')
        self.assertEqual(self.summary('研发岗位', 1, row)['result'], 'passed')
        self.assertEqual(row.to_dict()['primaryPosition']['position'], '研究岗位')
        self.assertEqual(self.application_record(), before_application)
        self.assertEqual(self.group_snapshot('研究岗位', 2), current)
        self.assertEqual(self.group_snapshot('Coding 岗位', 2), same_version)

    def test_two_names_in_the_same_version_can_be_changed_independently(self):
        before = self.group_snapshot('研究岗位', 2)
        row = self.change('Coding 岗位', 2, 'interviewing')
        summary = self.summary('Coding 岗位', 2, row)
        self.assertEqual((summary['status'], summary['result']), ('interviewing', 'passed'))
        self.assertEqual(len(summary['statusHistoryIds']), 1)
        self.assertEqual(self.group_snapshot('研究岗位', 2), before)

    def test_current_position_syncs_compatibility_state_without_changing_primary(self):
        service.set_primary_position(self.db, self.app_id, PrimaryPositionInput(
            position='研发岗位', position_version=1, expected_position_version=2))
        historical = self.group_snapshot('研发岗位', 1)
        row = self.change('研究岗位', 2, 'interviewing')
        self.assertEqual(row.status, 'interviewing')
        self.assertEqual(row.to_dict()['primaryPosition']['position'], '研发岗位')
        self.assertEqual(self.summary('研究岗位', 2, row)['status'], 'interviewing')
        self.assertEqual(self.group_snapshot('研发岗位', 1), historical)

    def test_same_name_in_another_version_stays_separate(self):
        service.update_application(self.db, self.app_id, ApplicationUpdate(position='研发岗位', restart_process=True))
        current = self.group_snapshot('研发岗位', 3)
        self.change('研发岗位', 1, 'interviewing')
        self.assertEqual(self.group_snapshot('研发岗位', 3), current)
        self.assertEqual(self.summary('研发岗位', 3)['status'], 'screening')

    def test_failed_results_and_backwards_changes_preserve_recorded_results(self):
        row = self.fresh()
        item = position_groups(row)[(1, '研发岗位')].rounds[0]
        service.update_round(self.db, item.id, RoundUpdate(result='failed'))
        self.change('研发岗位', 1, 'interviewing')
        self.change('研发岗位', 1, 'screening')
        self.assertEqual(self.summary('研发岗位', 1)['result'], 'failed')

    def test_same_value_retry_does_not_duplicate_history(self):
        payload = self.request('研发岗位', 1, 'interviewing')
        service.patch_position_status(self.db, self.app_id, payload)
        before = self.all_records()
        service.patch_position_status(self.db, self.app_id, payload)
        self.assertEqual(self.all_records(), before)

    def test_stale_status_history_is_rejected_even_when_old_status_returns(self):
        stale = self.request('研发岗位', 1, 'interviewing')
        self.change('研发岗位', 1, 'screening')
        self.change('研发岗位', 1, 'rescreen')
        before = self.all_records()
        with self.assertRaises(HTTPException) as error:
            service.patch_position_status(self.db, self.app_id, stale)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.all_records(), before)

    def test_stale_application_version_and_missing_target_do_not_write(self):
        original = self.request('研发岗位', 1, 'interviewing')
        for update in ({'expected_position_version': 1}, {'position': '已更名的旧目标'}):
            before = self.all_records()
            with self.subTest(update=update), self.assertRaises(HTTPException) as error:
                service.patch_position_status(self.db, self.app_id, original.model_copy(update=update))
            self.assertEqual(error.exception.status_code, 409)
            self.assertEqual(self.all_records(), before)

    def test_current_stage_is_reused_after_another_positions_status_changes(self):
        before = self.summary('研究岗位', 2)['statusHistoryIds']
        self.change('研发岗位', 1, 'interviewing')
        service.create_round(self.db, self.app_id, RoundCreate(round_type='written_test'))
        self.assertEqual(self.summary('研究岗位', 2)['statusHistoryIds'], before)

    def test_unknown_legacy_position_can_keep_its_own_status(self):
        row = service.create_application(self.db, ApplicationCreate(company='未知岗位示例', position=None))
        row = service.update_application(self.db, row.id, ApplicationUpdate(position='新岗位', restart_process=True))
        payload = self.request(None, 1, 'rescreen', row=self.fresh(row.id))
        row = service.patch_position_status(self.db, row.id, payload)
        self.assertEqual(self.summary(None, 1, row)['status'], 'rescreen')
        self.assertEqual((row.position, row.status), ('新岗位', 'screening'))
        self.assertTrue(all(item.position is None for item in row.status_history if item.position_version == 1))

    def test_deprecated_legacy_status_can_be_changed_and_stays_in_old_history(self):
        row = self.fresh()
        old_stage = position_groups(row)[(1, '研发岗位')].stages[-1]
        old_stage_id = old_stage.id
        old_stage.status = 'rejected'
        self.db.commit()
        payload = self.request('研发岗位', 1, 'rescreen')
        self.assertEqual(payload.expected_status, 'rejected')
        row = service.patch_position_status(self.db, self.app_id, payload)
        self.assertEqual(self.summary('研发岗位', 1, row)['status'], 'rescreen')
        self.assertEqual(next(item.status for item in row.status_history if item.id == old_stage_id), 'rejected')
        self.assertEqual(row.to_dict()['primaryPosition']['position'], '研究岗位')

    def test_deleted_position_cannot_be_recreated_by_status_request(self):
        row = self.fresh()
        payload = self.request('Coding 岗位', 2, 'interviewing')
        group = position_groups(row)[(2, 'Coding 岗位')]
        service.delete_position(self.db, self.app_id, PositionDeleteInput(
            position='Coding 岗位', position_version=2, expected_position_version=2,
            expected_round_ids=[item.id for item in group.rounds],
            expected_status_history_ids=[item.id for item in group.stages],
            expected_result_history_ids=[item.id for item in group.results],
        ))
        before = self.all_records()
        with self.assertRaises(HTTPException) as error:
            service.patch_position_status(self.db, self.app_id, payload)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.all_records(), before)

    def test_http_route_validates_context_and_keeps_legacy_current_route(self):
        payload = self.request('Coding 岗位', 2, 'interviewing').model_dump(by_alias=True)
        with patch.dict(app.dependency_overrides, {database.get_db: lambda: self.db}):
            client = TestClient(app)
            path = f'/api/jobs/applications/{self.app_id}/positions/status'
            response = client.patch(path, json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['status'], 'rescreen')
            self.assertEqual(self.summary('Coding 岗位', 2)['status'], 'interviewing')
            for field in ('position', 'expectedPositionVersion', 'expectedStatus', 'expectedStatusHistoryId'):
                invalid = dict(payload)
                invalid.pop(field)
                self.assertEqual(client.patch(path, json=invalid).status_code, 422)
            self.assertEqual(client.patch(path, json={**payload, 'status': 'unknown'}).status_code, 422)
            self.assertEqual(client.patch(f'/api/jobs/applications/{self.app_id}/status', json={'status': 'interviewing'}).status_code, 200)
            self.assertEqual(self.fresh().status, 'interviewing')
