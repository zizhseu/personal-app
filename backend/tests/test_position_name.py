"""岗位整组补名、更名、历史隔离和失败回滚，使用独立内存库。"""
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
from app.modules.jobs.models import InterviewRound, StatusHistory
from app.modules.jobs.positions import position_groups
from app.modules.jobs.schemas import (
    ApplicationCreate, ApplicationStatusPatch, ApplicationUpdate, PositionDeleteInput,
    PositionRenameInput, PrimaryPositionInput, RoundCreate,
)
from app.shared.base import Base


class PositionNameTests(unittest.TestCase):
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

    def unknown_position(self):
        row = service.create_application(self.db, ApplicationCreate(company='岗位名称示例', position=None))
        service.patch_status(self.db, row.id, ApplicationStatusPatch(status='rescreen'))
        service.create_round(self.db, row.id, RoundCreate(
            round_type='written_test', result='completed',
            start_at=datetime(2026, 11, 1, 9), duration_minutes=120, review_note='保留复盘内容'))
        return self.fresh(row.id)

    def request(self, row, position, version, new_position):
        target = position_groups(row)[(version, position)]
        return PositionRenameInput(
            position=position, position_version=version, expected_position_version=row.position_version,
            new_position=new_position, expected_round_ids=[item.id for item in target.rounds],
            expected_status_history_ids=[item.id for item in target.stages],
            expected_result_history_ids=[item.id for item in target.results],
        )

    def snapshot(self):
        return {table: [dict(row) for row in self.db.execute(text(f'SELECT * FROM {table} ORDER BY id')).mappings()]
                for table in ('application', 'interview_round', 'status_history', 'round_result_history')}

    def assert_only_name_changed(self, before, request, *, current=False, primary=False):
        for row in before['application']:
            if current:
                row['position'] = request.new_position
            if primary:
                row['primary_position'] = request.new_position
        for table, ids in (
            ('interview_round', request.expected_round_ids),
            ('status_history', request.expected_status_history_ids),
            ('round_result_history', request.expected_result_history_ids),
        ):
            for row in before[table]:
                if row['id'] in ids:
                    row['position'] = request.new_position
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.db.execute(text('PRAGMA foreign_key_check')).all(), [])

    def test_fill_current_unknown_position_updates_all_snapshots_and_explicit_primary(self):
        row = self.unknown_position()
        row = service.set_primary_position(self.db, row.id, PrimaryPositionInput(
            position=None, position_version=1, expected_position_version=1))
        request = self.request(row, None, 1, '  金融科技岗  ')
        before = self.snapshot()
        row = service.rename_position(self.db, row.id, request)
        self.assertEqual(row.position, '金融科技岗')
        self.assertEqual(list(position_groups(row)), [(1, '金融科技岗')])
        self.assertEqual(row.to_dict()['primaryPosition']['position'], '金融科技岗')
        self.assert_only_name_changed(before, request, current=True, primary=True)

    def test_fill_historical_unknown_after_current_deleted_preserves_empty_current(self):
        row = self.unknown_position()
        row = service.update_application(self.db, row.id, ApplicationUpdate(position='后来的岗位', restart_process=True))
        row = self.fresh(row.id)
        current = position_groups(row)[(2, '后来的岗位')]
        row = service.delete_position(self.db, row.id, PositionDeleteInput(
            position='后来的岗位', position_version=2, expected_position_version=2,
            expected_round_ids=[item.id for item in current.rounds],
            expected_status_history_ids=[item.id for item in current.stages],
            expected_result_history_ids=[item.id for item in current.results]))
        row = service.set_primary_position(self.db, row.id, PrimaryPositionInput(
            position=None, position_version=1, expected_position_version=row.position_version))
        request = self.request(row, None, 1, '历史金融科技岗')
        before = self.snapshot()
        row = service.rename_position(self.db, row.id, request)
        self.assertFalse(row.has_current_position)
        self.assertIsNone(row.position)
        self.assertEqual(row.to_dict()['primaryPosition']['position'], '历史金融科技岗')
        self.assertEqual(list(position_groups(row)), [(1, '历史金融科技岗')])
        self.assert_only_name_changed(before, request, primary=True)

    def test_rename_historical_known_position_preserves_other_periods_with_same_name(self):
        row = service.create_application(self.db, ApplicationCreate(company='同名分期示例', position='岗位 A'))
        row = service.update_application(self.db, row.id, ApplicationUpdate(position='岗位 B', restart_process=True))
        row = service.update_application(self.db, row.id, ApplicationUpdate(position='岗位 A', restart_process=True))
        request = self.request(self.fresh(row.id), '岗位 A', 1, '岗位 B')
        before = self.snapshot()
        row = service.rename_position(self.db, row.id, request)
        self.assertEqual(row.position, '岗位 A')
        self.assertEqual(set(position_groups(row)), {(1, '岗位 B'), (2, '岗位 B'), (3, '岗位 A')})
        self.assert_only_name_changed(before, request)

    def split_positions(self):
        row = service.create_application(self.db, ApplicationCreate(company='同代次多名称示例', position='岗位 B', status='rescreen'))
        service.create_round(self.db, row.id, RoundCreate(round_type='written_test', result='completed'))
        stage_a = StatusHistory(application_id=row.id, position='岗位 A', position_version=1, status='rescreen')
        unknown_stage = StatusHistory(application_id=row.id, position=None, position_version=1, status='rescreen')
        self.db.add_all([stage_a, unknown_stage])
        self.db.flush()
        self.db.add_all([
            InterviewRound(application_id=row.id, position=None, position_version=1, round_type='written_test',
                           result='not_started', status_history_id=stage_a.id),
            InterviewRound(application_id=row.id, position=None, position_version=1, round_type='assessment',
                           result='not_started', status_history_id=unknown_stage.id),
        ])
        self.db.commit()
        return self.fresh(row.id)

    def test_same_version_unknown_and_linked_records_can_be_renamed_independently(self):
        row = self.split_positions()
        for position, name in ((None, '补填岗位 C'), ('岗位 A', '更正岗位 A')):
            request = self.request(row, position, 1, name)
            before = self.snapshot()
            row = service.rename_position(self.db, row.id, request)
            self.assert_only_name_changed(before, request)
            self.assertEqual(set(position_groups(row)), {(1, '岗位 B'), (1, '补填岗位 C'), (1, '岗位 A' if position is None else name)})

    def test_same_version_name_collision_is_rejected_without_merging(self):
        row = self.split_positions()
        request = self.request(row, '岗位 A', 1, '岗位 B')
        before = self.snapshot()
        with self.assertRaises(HTTPException) as error:
            service.rename_position(self.db, row.id, request)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.snapshot(), before)

    def test_identical_request_retry_is_idempotent(self):
        row = self.unknown_position()
        request = self.request(row, None, 1, '已补填的岗位')
        service.rename_position(self.db, row.id, request)
        before = self.snapshot()
        service.rename_position(self.db, row.id, request)
        self.assertEqual(self.snapshot(), before)
        same_name = self.request(self.fresh(row.id), '已补填的岗位', 1, '已补填的岗位')
        service.rename_position(self.db, row.id, same_name)
        self.assertEqual(self.snapshot(), before)

    def test_stale_members_or_version_are_rejected_without_writes(self):
        row = self.unknown_position()
        stale = self.request(row, None, 1, '补填岗位')
        service.create_round(self.db, row.id, RoundCreate(round_type='assessment'))
        before = self.snapshot()
        with self.assertRaises(HTTPException) as error:
            service.rename_position(self.db, row.id, stale)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.snapshot(), before)
        current = self.request(self.fresh(row.id), None, 1, '补填岗位')
        service.update_application(self.db, row.id, ApplicationUpdate(position='新岗位', restart_process=True))
        before = self.snapshot()
        with self.assertRaises(HTTPException) as error:
            service.rename_position(self.db, row.id, current)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.snapshot(), before)

    def test_missing_duplicate_members_or_old_name_are_rejected(self):
        row = self.unknown_position()
        request = self.request(row, None, 1, '补填岗位')
        invalid_values = [
            {'position': '不存在的岗位'},
            {'expected_round_ids': None},
            {'expected_status_history_ids': []},
            {'expected_result_history_ids': []},
            {'expected_round_ids': request.expected_round_ids * 2},
        ]
        for values in invalid_values:
            before = self.snapshot()
            with self.subTest(values=values), self.assertRaises(HTTPException) as error:
                service.rename_position(self.db, row.id, request.model_copy(update=values))
            self.assertEqual(error.exception.status_code, 409)
            self.assertEqual(self.snapshot(), before)

    def test_partial_failure_rolls_back_current_and_round_updates(self):
        row = self.unknown_position()
        request = self.request(row, None, 1, '事务回滚示例')
        before = self.snapshot()
        execute = self.db.execute

        def fail_status_update(statement, *args, **kwargs):
            if getattr(statement, 'is_update', False) and statement.table.name == 'status_history':
                raise RuntimeError('模拟写入状态快照时失败')
            return execute(statement, *args, **kwargs)

        with patch.object(self.db, 'execute', side_effect=fail_status_update):
            with self.assertRaises(RuntimeError):
                service.rename_position(self.db, row.id, request)
        self.assertEqual(self.snapshot(), before)

    def test_http_route_and_name_validation(self):
        row = self.unknown_position()
        payload = self.request(row, None, 1, 'HTTP 补填岗位').model_dump(by_alias=True)
        with patch.dict(app.dependency_overrides, {database.get_db: lambda: self.db}):
            client = TestClient(app)
            path = f'/api/jobs/applications/{row.id}/positions/name'
            for name in ('', '   ', None, '岗' * 101):
                self.assertEqual(client.patch(path, json={**payload, 'newPosition': name}).status_code, 422)
            response = client.patch(path, json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['position'], 'HTTP 补填岗位')
            self.assertEqual(len(response.json()['positionSummaries']), 1)
            self.assertEqual(client.patch(path, json=payload).status_code, 200)
            self.assertEqual(client.patch('/api/jobs/applications/999/positions/name', json=payload).status_code, 404)


if __name__ == '__main__':
    unittest.main()
