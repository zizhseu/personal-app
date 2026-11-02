import {test} from 'node:test'
import assert from 'node:assert/strict'
import {groupPositionHistory} from '../src/modules/jobs/history.ts'
import {primaryApplication} from '../src/modules/jobs/primaryPosition.ts'
import {latestRound,currentResult} from '../src/modules/jobs/selectors.ts'

const app=()=>({id:1,company:'示例公司',position:'研究岗位',positionVersion:2,hasCurrentPosition:true,status:'rescreen',offerDecision:null,
  rounds:[{id:1,position:'研发岗位',positionVersion:1,roundType:'written_test',result:'failed',createdAt:'2026-10-01T10:00:00'},
    {id:2,position:'研究岗位',positionVersion:2,roundType:'assessment',result:'completed',createdAt:'2026-10-27T10:00:00'},
    {id:3,position:'Coding 岗位',positionVersion:2,roundType:'first',result:'not_started',createdAt:'2026-11-02T10:00:00'}],
  statusHistory:[{id:1,position:'研究岗位',positionVersion:2,status:'rescreen',changedAt:'2026-10-27T09:00:00'}],resultHistory:[]})
const summary=()=>({position:'Coding 岗位',positionVersion:2,displayOrder:3,isCurrent:false,isPrimary:true,status:'interviewing',result:'not_started',offerDecision:null,latestRoundId:3,roundIds:[3],statusHistoryIds:[],resultHistoryIds:[]})

test('同一内部版本的不同岗位有独立展示序号，切换主要岗位不会改变序号或合并记录',()=>{
  const source=app()
  const before=groupPositionHistory(source)
  assert.equal(new Set(before.map(row=>row.displayOrder)).size,3)
  const orders=new Map(before.map(row=>[row.key,row.displayOrder]))
  source.primaryPosition=summary()
  const after=groupPositionHistory(source)
  assert.equal(after[0].position,'Coding 岗位')
  assert.equal(after[0].isPrimary,true)
  for(const group of after)assert.equal(group.displayOrder,orders.get(group.key))
})

test('列表投影的名称、状态、最新轮次和结果来自主要岗位，不改写原始当前岗位',()=>{
  const source=app();source.primaryPosition=summary()
  const original=structuredClone(source)
  const view=primaryApplication(source)
  assert.equal(view.position,'Coding 岗位')
  assert.equal(view.status,'interviewing')
  assert.equal(view.displayIsCurrent,false)
  assert.equal(latestRound(view).roundType,'first')
  assert.equal(currentResult(view),'not_started')
  assert.equal(view.rounds.length,1)
  assert.deepEqual(source,original)
})

test('当前岗位删除后，显式保留的历史主要岗位仍可汇总；无选择时保持空公司',()=>{
  const source={...app(),position:null,positionVersion:4,hasCurrentPosition:false,primaryPosition:summary()}
  assert.equal(primaryApplication(source).position,'Coding 岗位')
  source.primaryPosition=null
  const view=primaryApplication(source)
  assert.equal(view.hasCurrentPosition,false)
  assert.equal(latestRound(view),null)
})

test('主要岗位没有已记录的状态时不会把当前岗位状态当作历史事实显示',()=>{
  const source=app();source.primaryPosition={...summary(),status:null}
  assert.equal(primaryApplication(source).displayStatusRecorded,false)
})
