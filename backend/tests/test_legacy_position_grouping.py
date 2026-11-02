"""旧版空岗位快照的兼容归组；不通过回填数据库掩盖归组错误。"""
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import app  # noqa: F401，注册全部模型与 SQLite 外键检查。
from app.modules.jobs import service
from app.modules.jobs.models import StatusHistory
from app.modules.jobs.positions import position_groups
from app.modules.jobs.schemas import ApplicationCreate, ApplicationUpdate, PositionDeleteInput, RoundCreate
from app.shared.base import Base


class LegacyPositionGroupingTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False, expire_on_commit=False)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def legacy(self):
        row = service.create_application(self.db, ApplicationCreate(company='旧版投递示例', position='数据岗位', status='interviewing'))
        item = service.create_round(self.db, row.id, RoundCreate(round_type='first', result='not_attended'))
        self.db.expire_all()
        row = service.get_application(self.db, row.id)
        for records in (row.rounds, row.status_history, row.round_result_history):
            for record in records:
                record.position = None
        row.status_history.append(StatusHistory(position=None, position_version=1, status='screening'))
        self.db.commit()
        self.db.expire_all()
        return service.get_application(self.db, row.id), item.id

    def test_single_flow_legacy_records_are_one_position_without_persisting_inferred_name(self):
        row, item_id = self.legacy()
        before = row.to_dict()
        groups = position_groups(row)
        self.assertEqual(set(groups), {(1,'数据岗位')})
        group = groups[(1,'数据岗位')]
        self.assertEqual([item.id for item in group.rounds], [item_id])
        self.assertEqual(len(group.stages), 2)
        self.assertEqual(len(group.results), 1)
        self.assertTrue(service._current_round(group.rounds[0], row))
        self.assertEqual(row.to_dict(), before)
        self.assertTrue(all(record.position is None for records in (row.rounds,row.status_history,row.round_result_history) for record in records))

    def test_adding_round_reuses_matching_legacy_stage_instead_of_duplicating_status(self):
        row, _ = self.legacy()
        # 保证最近一条状态与当前面试状态一致，模拟用户截图中的正常时间顺序。
        interview = next(item for item in row.status_history if item.status=='interviewing')
        screening = next(item for item in row.status_history if item.status=='screening')
        screening.changed_at = interview.changed_at.replace(year=interview.changed_at.year-1)
        self.db.commit()
        value = service.create_round(self.db, row.id, RoundCreate(round_type='second'))
        self.db.expire_all()
        row = service.get_application(self.db, row.id)
        self.assertEqual(value.status_history_id, interview.id)
        self.assertEqual(len(row.status_history),2)

    def test_no_inference_across_versions_and_same_name_reapplications_remain_separate(self):
        row, _ = self.legacy()
        service.update_application(self.db,row.id,ApplicationUpdate(position='岗位 B',restart_process=True))
        self.db.expire_all()
        row=service.get_application(self.db,row.id)
        self.assertEqual(set(position_groups(row)),{(1,None),(2,'岗位 B')})
        row.status_history[0].position='数据岗位'
        self.db.commit()
        service.update_application(self.db,row.id,ApplicationUpdate(position='数据岗位',restart_process=True))
        self.db.expire_all()
        self.assertEqual(set(position_groups(service.get_application(self.db,row.id))),{(1,'数据岗位'),(2,'岗位 B'),(3,'数据岗位')})

    def test_multiple_known_names_do_not_force_unknown_records_into_current_position(self):
        row,_=self.legacy()
        row.status_history.append(StatusHistory(position='另一个岗位',position_version=1,status='interviewing'))
        self.db.commit()
        self.assertEqual(set(position_groups(row)),{(1,'数据岗位'),(1,'另一个岗位'),(1,None)})
        self.assertFalse(service._current_round(row.rounds[0],row))

    def test_stale_empty_group_or_old_client_cannot_delete_regrouped_legacy_history(self):
        row,_=self.legacy()
        before=row.to_dict()
        for scope in ({}, {'expected_round_ids':[], 'expected_status_history_ids':[], 'expected_result_history_ids':[]}):
            with self.subTest(scope=scope),self.assertRaises(HTTPException) as error:
                service.delete_position(self.db,row.id,PositionDeleteInput(position='数据岗位',position_version=1,expected_position_version=1,**scope))
            self.assertEqual(error.exception.status_code,409)
            self.assertEqual(row.to_dict(),before)

        # 旧页面还保留「岗位未记录」卡片时，即使携带原成员也不能删除其新归属。
        with self.assertRaises(HTTPException) as error:
            service.delete_position(self.db,row.id,PositionDeleteInput(position=None,position_version=1,expected_position_version=1,
                expected_round_ids=[item['id'] for item in before['rounds']],expected_status_history_ids=[item['id'] for item in before['statusHistory']],
                expected_result_history_ids=[item['id'] for item in before['resultHistory']]))
        self.assertEqual(error.exception.status_code,409)
        self.assertEqual(row.to_dict(),before)

    def test_changed_membership_requires_confirmation_again_even_if_position_version_is_same(self):
        row,_=self.legacy()
        scope=position_groups(row)[(1,'数据岗位')]
        payload=PositionDeleteInput(position='数据岗位',position_version=1,expected_position_version=1,
            expected_round_ids=[item.id for item in scope.rounds],expected_status_history_ids=[item.id for item in scope.stages],
            expected_result_history_ids=[item.id for item in scope.results])
        service.create_round(self.db,row.id,RoundCreate(round_type='first'))
        self.db.expire_all()
        row=service.get_application(self.db,row.id)
        before=row.to_dict()
        with self.assertRaises(HTTPException) as error:
            service.delete_position(self.db,row.id,payload)
        self.assertEqual(error.exception.status_code,409)
        self.assertEqual(row.to_dict(),before)
