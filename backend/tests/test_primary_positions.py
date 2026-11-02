"""主要岗位是展示选择，不改变当前流程与历史；同代次不同名称有独立展示序号。"""
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core import database
from app.modules.jobs import service
from app.modules.jobs.positions import position_groups, position_summaries
from app.modules.jobs.schemas import ApplicationCreate, ApplicationUpdate, ApplicationStatusPatch, PrimaryPositionInput, RoundCreate, RoundUpdate, PositionDeleteInput
from app.shared.base import Base


class PrimaryPositionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://', connect_args={'check_same_thread':False}, poolclass=StaticPool)
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine, autoflush=False, expire_on_commit=False)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def fresh(self, app_id):
        self.db.expire_all()
        return service.get_application(self.db, app_id)

    def example(self):
        row = service.create_application(self.db, ApplicationCreate(company='主要岗位示例', position='研发岗位', status='rescreen', note='公司备注'))
        service.create_round(self.db,row.id,RoundCreate(round_type='written_test',result='failed'))
        row = service.update_application(self.db,row.id,ApplicationUpdate(position='研究岗位',restart_process=True))
        row = self.fresh(row.id)
        initial = next(item for item in row.rounds if item.position_version==2)
        service.update_round(self.db,initial.id,RoundUpdate(position='Coding 岗位',result='passed'))
        service.patch_status(self.db,row.id,ApplicationStatusPatch(status='rescreen'))
        service.create_round(self.db,row.id,RoundCreate(position='Coding 岗位',position_version=2,round_type='written_test',result='completed'))
        service.create_round(self.db,row.id,RoundCreate(position='Coding 岗位',position_version=2,round_type='first',result='completed'))
        service.create_round(self.db,row.id,RoundCreate(round_type='assessment',result='completed'))
        return self.fresh(row.id)

    def choose(self,row,position,version):
        return service.set_primary_position(self.db,row.id,PrimaryPositionInput(position=position,position_version=version,expected_position_version=row.position_version))

    def original_data(self):
        values={}
        for table in ('application','interview_round','status_history','round_result_history'):
            columns=[item[1] for item in self.db.execute(text('PRAGMA table_info('+table+')')) if item[1] not in ('primary_position','primary_position_version')]
            values[table]=self.db.execute(text('SELECT '+','.join(columns)+' FROM '+table+' ORDER BY id')).all()
        return values

    def remove(self,row,position,version):
        group=position_groups(row)[(version,position)]
        return service.delete_position(self.db,row.id,PositionDeleteInput(position=position,position_version=version,expected_position_version=row.position_version,
            expected_round_ids=[item.id for item in group.rounds],expected_status_history_ids=[item.id for item in group.stages],expected_result_history_ids=[item.id for item in group.results]))

    def test_same_internal_version_has_unique_display_order_and_default_primary(self):
        row=self.example()
        summaries=position_summaries(row)
        self.assertEqual(len(summaries),3)
        self.assertEqual([item['displayOrder'] for item in summaries],[1,2,3])
        self.assertEqual(sum(item['positionVersion']==2 for item in summaries),2)
        primary=row.to_dict()['primaryPosition']
        self.assertEqual((primary['position'],primary['status']),('研究岗位','rescreen'))
        self.assertEqual(len(primary['roundIds']),1)

    def test_selecting_same_version_historical_position_only_updates_preference(self):
        row=self.example()
        before=self.original_data()
        orders={(item['positionVersion'],item['position']):item['displayOrder'] for item in position_summaries(row)}
        row=self.choose(row,'Coding 岗位',2)
        primary=row.to_dict()['primaryPosition']
        self.assertEqual((primary['position'],primary['status'],primary['result']),('Coding 岗位','interviewing','completed'))
        self.assertEqual(len(primary['roundIds']),3)
        self.assertFalse(primary['isCurrent'])
        self.assertEqual((row.position,row.position_version,row.status),('研究岗位',2,'rescreen'))
        self.assertEqual(self.original_data(),before)
        self.assertEqual({(item['positionVersion'],item['position']):item['displayOrder'] for item in position_summaries(row)},orders)
        self.assertEqual(self.fresh(row.id).to_dict()['primaryPosition']['position'],'Coding 岗位')

    def test_primary_selection_persists_when_another_position_is_created(self):
        row=self.choose(self.example(),'研发岗位',1)
        row=service.update_application(self.db,row.id,ApplicationUpdate(position='研发岗位',restart_process=True))
        self.assertEqual(row.position_version,3)
        self.assertEqual(row.to_dict()['primaryPosition']['positionVersion'],1)
        row=self.choose(self.fresh(row.id),'研发岗位',3)
        self.assertEqual(row.to_dict()['primaryPosition']['positionVersion'],3)

    def test_round_only_position_can_infer_status_without_creating_status_rows(self):
        row=service.create_application(self.db,ApplicationCreate(company='无阶段示例',position='当前岗位',status='interviewing'))
        item=service.create_round(self.db,row.id,RoundCreate(round_type='first'))
        service.update_round(self.db,item.id,RoundUpdate(position='历史岗位'))
        row=self.fresh(row.id)
        before=len(row.status_history)
        row=self.choose(row,'历史岗位',1)
        self.assertEqual(row.to_dict()['primaryPosition']['status'],'interviewing')
        self.assertEqual(len(row.status_history),before)

    def test_deleting_selected_history_falls_back_to_current(self):
        row=self.choose(self.example(),'Coding 岗位',2)
        row=self.remove(row,'Coding 岗位',2)
        self.assertIsNone(row.primary_position_version)
        self.assertEqual(row.to_dict()['primaryPosition']['position'],'研究岗位')

    def test_deleting_current_keeps_other_selected_primary_without_reactivating_current(self):
        row=self.choose(self.example(),'研发岗位',1)
        row=self.remove(row,'研究岗位',2)
        self.assertFalse(row.has_current_position)
        self.assertEqual(row.to_dict()['primaryPosition']['position'],'研发岗位')
        row=self.remove(row,'研发岗位',1)
        self.assertIsNone(row.to_dict()['primaryPosition'])

    def test_stale_and_missing_target_requests_do_not_write(self):
        row=self.example()
        before=self.original_data()
        for values in [dict(position='不存在',position_version=2,expected_position_version=2),
                       dict(position='Coding 岗位',position_version=2,expected_position_version=1)]:
            with self.subTest(values=values),self.assertRaises(HTTPException) as error:
                service.set_primary_position(self.db,row.id,PrimaryPositionInput(**values))
            self.assertEqual(error.exception.status_code,409)
            self.assertEqual(self.original_data(),before)

    def test_unknown_old_position_and_repeated_choice_are_supported(self):
        row=service.create_application(self.db,ApplicationCreate(company='未知旧岗位',position=None))
        row=service.update_application(self.db,row.id,ApplicationUpdate(position='新岗位',restart_process=True))
        before=self.original_data()
        for _ in range(2):
            row=self.choose(self.fresh(row.id),None,1)
        self.assertIsNone(row.to_dict()['primaryPosition']['position'])
        self.assertEqual(row.to_dict()['primaryPosition']['positionVersion'],1)
        self.assertEqual(self.original_data(),before)

    def test_http_selection_validation_and_history_preservation(self):
        row=self.example()
        with patch.dict(app.dependency_overrides,{database.get_db:lambda:self.db}):
            client=TestClient(app)
            path=f'/api/jobs/applications/{row.id}/primary-position'
            value=client.put(path,json={'position':'Coding 岗位','positionVersion':2,'expectedPositionVersion':2})
            self.assertEqual(value.status_code,200)
            self.assertEqual(value.json()['primaryPosition']['position'],'Coding 岗位')
            self.assertEqual(value.json()['position'],'研究岗位')
            for body in [{'position':'Coding 岗位','positionVersion':0,'expectedPositionVersion':2},
                         {'positionVersion':2,'expectedPositionVersion':2},
                         {'position':'Coding 岗位','positionVersion':2,'expectedPositionVersion':2,'restartProcess':True}]:
                self.assertEqual(client.put(path,json=body).status_code,422)
