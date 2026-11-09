"""jobs 模块业务逻辑。"""
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.modules.jobs.constants import ROUND_TYPE_LABELS, ROUND_TYPE_STATUS, STATUS_FLOW, STATUS_LABELS
from app.modules.jobs.models import (
    Application,
    InterviewRound,
    RoundResultHistory,
    ScheduleEvent,
    StatusHistory,
)
from app.modules.jobs.schemas import (
    ApplicationCreate,
    ApplicationStatusPatch,
    ApplicationUpdate,
    EventCreate,
    EventUpdate,
    OfferDecisionPatch,
    PositionDeleteInput,
    PositionRenameInput,
    PrimaryPositionInput,
    PositionStatusPatch,
    RoundCreate,
    RoundUpdate,
    StatusHistoryPositionInput,
)
from app.modules.jobs.positions import PositionResolver, position_groups, position_summaries, recorded_position


def list_applications(
    db: Session,
    status: str | None = None,
    keyword: str | None = None,
) -> list[Application]:
    """全量列表（含轮次、状态历史），按投递日期倒序、空日期在后。"""
    stmt = select(Application).options(
        joinedload(Application.rounds),
        joinedload(Application.status_history),
        joinedload(Application.round_result_history),
    )
    if status:
        stmt = stmt.where(Application.status == status)
    if keyword:
        like = f"%{keyword}%"
        stmt = stmt.where(Application.company.like(like) | Application.position.like(like))
    stmt = stmt.order_by(Application.apply_date.is_not(None), Application.apply_date.desc())
    rows = list(db.scalars(stmt).unique().all())
    return [row for row in rows if not status or row.has_current_position]


def get_application(db: Session, app_id: int) -> Application:
    stmt = (
        select(Application)
        .options(
            joinedload(Application.rounds),
            joinedload(Application.status_history),
            joinedload(Application.round_result_history),
        )
        .where(Application.id == app_id)
    )
    app_row = db.scalars(stmt).unique().first()
    if app_row is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return app_row


def _new_stage(db: Session, row: Application, status: str, when: datetime) -> StatusHistory:
    stage = StatusHistory(status=status, changed_at=when, position=row.position, position_version=row.position_version)
    row.status_history.append(stage)
    db.flush()
    return stage


def _current_stage(db: Session, row: Application, when: datetime) -> StatusHistory:
    resolver = PositionResolver(row)
    candidates = [h for h in row.status_history if h.position_version == row.position_version
                  and resolver.stage_position(h) == recorded_position(row.position)]
    latest = max(candidates, key=lambda h: (h.changed_at, h.id), default=None)
    if latest and latest.status == row.status:
        return latest
    return _new_stage(db, row, row.status, when)


def _current_round(round_row: InterviewRound, app_row: Application) -> bool:
    if round_row.position_version != app_row.position_version:
        return False
    return PositionResolver(app_row).round_position(round_row) == recorded_position(app_row.position)


def _round_stage(db: Session, round_row: InterviewRound, app_row: Application, when: datetime) -> StatusHistory | None:
    if _current_round(round_row, app_row):
        return _current_stage(db, app_row, when)
    if round_row.status_history_id:
        return db.get(StatusHistory, round_row.status_history_id)
    resolver = PositionResolver(app_row)
    candidates = [h for h in app_row.status_history if h.position_version == round_row.position_version
                  and h.status == ROUND_TYPE_STATUS.get(round_row.round_type) and h.changed_at <= when
                  and resolver.stage_position(h) == resolver.round_position(round_row)]
    return max(candidates, key=lambda h: (h.changed_at, h.id), default=None)


def _record_result(db: Session, round_row: InterviewRound, stage: StatusHistory | None,
                   old_result: str | None, when: datetime) -> None:
    db.add(RoundResultHistory(round_id=round_row.id, application_id=round_row.application_id,
        status=stage.status if stage else ROUND_TYPE_STATUS.get(round_row.round_type, "screening"),
        status_history_id=stage.id if stage else None, position=round_row.position,
        position_version=round_row.position_version, from_result=old_result,
        to_result=round_row.result, changed_at=when))


def _sync_rounds_on_status_change(
    db: Session, row: Application, old_status: str | None, new_status: str, stage: StatusHistory, when: datetime,
    rounds: list[InterviewRound] | None = None,
) -> None:
    """状态正向推进时，只把所选岗位最新轮次置为「通过」。
    边界：倒退/平移不联动；「未通过」是用户录入的事实不覆盖；无轮次静默跳过。
    下一环节的新轮次默认「未开始」（前后端默认值），无需在此处理。
    """
    if old_status not in STATUS_FLOW or new_status not in STATUS_FLOW:
        return
    if STATUS_FLOW.index(new_status) <= STATUS_FLOW.index(old_status):
        return
    scoped_rounds = rounds if rounds is not None else [r for r in row.rounds if _current_round(r, row)]
    if scoped_rounds:
        latest = max(scoped_rounds, key=lambda r: r.id)
        if latest.result in ("not_started", "completed", "not_attended"):
            old = latest.result
            latest.result = "passed"
            latest.result_changed_at = when
            _record_result(db, latest, stage, old, when)


def create_application(db: Session, data: ApplicationCreate) -> Application:
    row = Application(**data.model_dump(), position_version=1)
    db.add(row)
    db.flush()
    # 初始状态也记一条历史（如：投递中 → 2026-09-10 15:30）
    stage = _new_stage(db, row, row.status, datetime.now())
    # 初筛状态下自动添加默认的「初筛」轮次：流程时间线从投递创建即有起点
    # （结果未开始、时间待定，后续可编辑；状态推进到复筛时会被联动置「通过」）
    if row.status == "screening":
        row.rounds.append(InterviewRound(round_type="screening", result="not_started", position=row.position,
                                       position_version=row.position_version, status_history_id=stage.id))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_application(db: Session, app_id: int, data: ApplicationUpdate) -> Application:
    row = get_application(db, app_id)
    updates = data.model_dump(exclude_unset=True)
    restart = updates.pop("restart_process", False)
    expected = updates.pop("expected_position_version", None)
    if expected is not None and expected != row.position_version:
        raise HTTPException(409, "岗位已在其他操作中变更，请刷新记录后重试")
    position_changed = "position" in updates and updates["position"] != (row.position.strip() or None if row.position else None)
    new_position_period = position_changed or restart
    if not row.has_current_position and not new_position_period and updates.get("status", row.status) != row.status:
        raise HTTPException(422, "请先新增岗位，再设置状态")
    when = datetime.now()
    old_status = row.status  # 先取旧状态（setattr 会覆盖）
    if new_position_period:
        previous_version = row.position_version
        result = db.execute(update(Application).where(Application.id == row.id,
            Application.position_version == previous_version).values(position_version=previous_version + 1))
        if result.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "岗位已变更，请刷新记录后重试")
        row.position_version = previous_version + 1
        row.offer_decision = None
    if restart:
        updates["status"] = "screening"
    for key, value in updates.items():
        setattr(row, key, value)
    if new_position_period or row.status != old_status:
        stage = _new_stage(db, row, row.status, when)
        if not new_position_period:
            _sync_rounds_on_status_change(db, row, old_status, row.status, stage, when)
        elif row.status == "screening":
            row.rounds.append(InterviewRound(round_type="screening", result="not_started", position=row.position,
                position_version=row.position_version, status_history_id=stage.id))
    db.commit()
    db.refresh(row)
    return row


def patch_status(db: Session, app_id: int, data: ApplicationStatusPatch) -> Application:
    row = get_application(db, app_id)
    if not row.has_current_position:
        raise HTTPException(422, "请先新增岗位，再设置状态")
    if row.status != data.status:
        when, old_status = datetime.now(), row.status
        row.status = data.status
        stage = _new_stage(db, row, data.status, when)
        _sync_rounds_on_status_change(db, row, old_status, data.status, stage, when)
        db.commit()
        db.refresh(row)
    return row


def patch_position_status(db: Session, app_id: int, data: PositionStatusPatch) -> Application:
    """每个岗位独立追加状态，主要岗位选择不参与写入目标判断。"""
    get_application(db, app_id)
    try:
        # 先锁定父记录再读取分组，避免旧页面与并发更换/删除岗位交错写入。
        locked = db.execute(
            update(Application)
            .where(Application.id == app_id, Application.position_version == data.expected_position_version)
            .values(updated_at=Application.updated_at)
        )
        if locked.rowcount != 1:
            raise HTTPException(409, "岗位记录已变更，请刷新后重试")
        db.expire_all()
        row = get_application(db, app_id)
        key = (data.position_version, recorded_position(data.position))
        group = position_groups(row).get(key)
        if group is None:
            raise HTTPException(409, "所选岗位已变更或删除，请刷新后重试")
        summary = next(
            item for item in position_summaries(row)
            if (item['positionVersion'], item['position']) == key
        )
        latest_stage = max(group.stages, key=lambda item: (item.changed_at, item.id), default=None)
        # 同值重试不重复追加历史；不同值必须核对旧状态，拒绝覆盖较新的操作。
        if summary['status'] != data.status:
            if (summary['status'] != data.expected_status
                    or (latest_stage.id if latest_stage else None) != data.expected_status_history_id):
                raise HTTPException(409, "该岗位状态已更新，请刷新后重新选择")
            when = datetime.now()
            stage = StatusHistory(
                status=data.status, changed_at=when, position=key[1], position_version=key[0],
            )
            row.status_history.append(stage)
            if summary['isCurrent']:
                row.status = data.status
            db.flush()
            _sync_rounds_on_status_change(db, row, summary['status'], data.status, stage, when, rounds=group.rounds)
        db.commit()
        db.expire_all()
        return get_application(db, app_id)
    except Exception:
        db.rollback()
        raise


def patch_offer_decision(
    db: Session, app_id: int, data: OfferDecisionPatch
) -> Application:
    row = get_application(db, app_id)
    if row.status != "offer":
        raise HTTPException(status_code=422, detail="仅状态为「Offer」时可设置接受 / 拒绝")
    row.offer_decision = data.offer_decision
    db.commit()
    db.refresh(row)
    return row


def delete_application(db: Session, app_id: int) -> None:
    row = get_application(db, app_id)
    db.delete(row)
    db.commit()


def set_primary_position(db: Session, app_id: int, data: PrimaryPositionInput) -> Application:
    row = get_application(db, app_id)
    if row.position_version != data.expected_position_version:
        raise HTTPException(409, "岗位记录已变更，请刷新后重新选择主要岗位")
    key = (data.position_version, recorded_position(data.position))
    if key not in position_groups(row):
        raise HTTPException(409, "所选岗位已变更或删除，请刷新后重试")
    result = db.execute(update(Application).where(Application.id == app_id,
        Application.position_version == data.expected_position_version).values(
            primary_position=key[1], primary_position_version=key[0], updated_at=Application.updated_at))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "岗位记录已变更，请刷新后重试")
    db.commit()
    db.expire_all()
    return get_application(db, app_id)


def rename_position(db: Session, app_id: int, data: PositionRenameInput) -> Application:
    """在一次事务中更新所选岗位的名称及全部快照。"""
    get_application(db, app_id)
    try:
        locked = db.execute(update(Application).where(
            Application.id == app_id,
            Application.position_version == data.expected_position_version,
        ).values(updated_at=Application.updated_at))
        if locked.rowcount != 1:
            raise HTTPException(409, "岗位记录已变更，请刷新后重试")
        db.expire_all()
        row = get_application(db, app_id)
        groups = position_groups(row)
        key = (data.position_version, recorded_position(data.position))
        new_key = (data.position_version, data.new_position)
        target = groups.get(key)
        already_renamed = target is None
        if already_renamed:
            target = groups.get(new_key)
        if target is None:
            raise HTTPException(409, "所选岗位已变更或删除，请刷新后重试")
        members = (
            (InterviewRound, target.rounds, data.expected_round_ids),
            (StatusHistory, target.stages, data.expected_status_history_ids),
            (RoundResultHistory, target.results, data.expected_result_history_ids),
        )
        for _, items, expected in members:
            actual = {item.id for item in items}
            if expected is None or len(expected) != len(set(expected)) or set(expected) != actual:
                raise HTTPException(409, "岗位记录范围已更新，请刷新后重新编辑")
        # 完全相同的请求重试时，确认成员范围后直接返回。
        if already_renamed or key == new_key:
            db.commit()
            return row
        if new_key in groups:
            raise HTTPException(409, "同一流程已有该名称的岗位，请使用不同名称")
        values = {"updated_at": Application.updated_at}
        if row.has_current_position and key == (row.position_version, recorded_position(row.position)):
            values["position"] = data.new_position
        if key == (row.primary_position_version, recorded_position(row.primary_position)):
            values["primary_position"] = data.new_position
        db.execute(update(Application).where(Application.id == app_id).values(**values))
        for model, items, _ in members:
            db.execute(update(model).where(
                model.application_id == app_id,
                model.id.in_([item.id for item in items]),
            ).values(position=data.new_position, updated_at=model.updated_at))
        db.commit()
        db.expire_all()
        return get_application(db, app_id)
    except Exception:
        db.rollback()
        raise


def delete_position(db: Session, app_id: int, data: PositionDeleteInput) -> Application:
    row = get_application(db, app_id)
    if row.position_version != data.expected_position_version:
        raise HTTPException(409, "当前岗位已变更，请刷新后重新确认删除范围")
    groups = position_groups(row)
    key = (data.position_version, recorded_position(data.position))
    target = groups.get(key)
    if target is None:
        raise HTTPException(409, "该岗位流程已变更或删除，请刷新后重试")
    round_ids = {item.id for item in target.rounds}
    result_ids = {item.id for item in target.results}
    stage_ids = {item.id for item in target.stages}
    for expected, actual in ((data.expected_round_ids, round_ids), (data.expected_status_history_ids, stage_ids),
                             (data.expected_result_history_ids, result_ids)):
        if expected is None or len(expected) != len(set(expected)) or set(expected) != actual:
            raise HTTPException(409, "岗位记录范围已更新，请刷新页面后重新确认删除；本次未删除任何记录")
    if round_ids and db.scalar(select(RoundResultHistory.id).where(
            RoundResultHistory.round_id.in_(round_ids), RoundResultHistory.id.not_in(result_ids)).limit(1)) is not None:
        raise HTTPException(409, "存在其他岗位的结果关联，请先更正相关岗位后删除")
    # 异常的跨公司阶段关联也不应通过级联影响其他公司的记录。
    for model in (InterviewRound, RoundResultHistory):
        if stage_ids and db.scalar(select(model.id).where(model.status_history_id.in_(stage_ids),
                model.application_id != app_id).limit(1)) is not None:
            raise HTTPException(409, "存在其他公司的阶段关联，请先更正后删除")
    is_current = key == (row.position_version, recorded_position(row.position))
    values = {"position_version": row.position_version}
    if row.primary_position_version == key[0] and recorded_position(row.primary_position) == key[1]:
        values.update(primary_position=None, primary_position_version=None)
    if is_current:
        versions = [row.position_version, *(version for version, _ in groups)]
        values.update(position=None, position_version=max(versions) + 1, status="screening", offer_decision=None)
    changed = db.execute(update(Application).where(Application.id == app_id,
        Application.position_version == data.expected_position_version).values(**values))
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "岗位已变更，请刷新后重试")
    for items in (target.results, target.rounds, target.stages):
        for item in items:
            db.delete(item)
        db.flush()
    db.commit()
    db.expire_all()
    return get_application(db, app_id)


def _deadline(
    start_at: datetime | None, duration_minutes: int | None
) -> datetime | None:
    """截止时间 = 开始时间 + 持续时间；无开始时间则无截止。"""
    if start_at is None:
        return None
    return start_at + timedelta(minutes=duration_minutes or 0)


def _check_round_type_status(round_type: str, app_status: str | None) -> None:
    """硬约束：轮次类型必须与投递状态匹配（如面试轮次需状态为「面试中」）。"""
    required = ROUND_TYPE_STATUS.get(round_type)
    if required and app_status != required:
        raise HTTPException(
            status_code=422,
            detail=(
                f"需先将状态改为「{STATUS_LABELS[required]}」"
                f"才能添加「{ROUND_TYPE_LABELS[round_type]}」轮次"
            ),
        )


def create_round(db: Session, app_id: int, data: RoundCreate) -> InterviewRound:
    app_row = get_application(db, app_id)  # 确认父记录存在
    if data.expected_position_version is not None and data.expected_position_version != app_row.position_version:
        raise HTTPException(409, "当前岗位已变更，请刷新后确认所属岗位再添加")
    version = data.position_version if data.position_version is not None else app_row.position_version
    position = data.position if data.position_version is not None else app_row.position
    is_current = version == app_row.position_version and position == app_row.position
    if is_current and not app_row.has_current_position:
        raise HTTPException(409, "当前岗位已删除，请先新增岗位")
    when = datetime.now()
    if is_current:
        _check_round_type_status(data.round_type, app_row.status)
        stage = _current_stage(db, app_row, when)
    else:
        target = next((item for item in position_summaries(app_row)
                       if (item['positionVersion'], item['position']) == (version, recorded_position(position))), None)
        if target is None:
            raise HTTPException(409, "该岗位流程已变更或删除，请刷新后重试")
        if target['status'] == 'offer' or ROUND_TYPE_STATUS[data.round_type] == 'offer':
            _check_round_type_status(data.round_type, target['status'])
        # 历史补录不受当前岗位状态限制，只关联该岗位内与轮次类型匹配的阶段。
        resolver = PositionResolver(app_row)
        candidates = [h for h in app_row.status_history if h.position_version == version
                      and resolver.stage_position(h) == recorded_position(position) and h.status == ROUND_TYPE_STATUS.get(data.round_type)]
        stage = max(candidates, key=lambda h: (h.changed_at, h.id), default=None)
    payload = data.model_dump(exclude={"position", "position_version", "expected_position_version"})
    start_at = payload.pop("start_at")
    duration_minutes = payload.pop("duration_minutes")
    # 创建时若结果已不再是「未开始」，记录结果变更时间
    result_changed_at = when if payload.get("result", "not_started") != "not_started" else None
    row = InterviewRound(
        application_id=app_id,
        position=position,
        position_version=version,
        status_history_id=stage.id if stage else None,
        start_at=start_at,
        duration_minutes=duration_minutes,
        scheduled_at=_deadline(start_at, duration_minutes),
        result_changed_at=result_changed_at,
        **payload,
    )
    db.add(row)
    db.flush()  # 先取 row.id 供结果历史引用
    # 创建即有结果：记一条初始结果变化（from 为空）
    if result_changed_at is not None:
        _record_result(db, row, stage, None, when)
    db.commit()
    db.refresh(row)
    return row


def get_round(db: Session, round_id: int) -> InterviewRound:
    row = db.get(InterviewRound, round_id)
    if row is None:
        raise HTTPException(status_code=404, detail="轮次不存在")
    return row


def update_round(db: Session, round_id: int, data: RoundUpdate) -> InterviewRound:
    row = get_round(db, round_id)
    updates = data.model_dump(exclude_unset=True)
    # 改轮次类型时同样校验状态匹配
    new_type = updates.get("round_type") or row.round_type
    app_row = db.get(Application, row.application_id)
    when = datetime.now()
    if app_row is not None and new_type != row.round_type:
        stage = _round_stage(db, row, app_row, when)
        _check_round_type_status(new_type, stage.status if stage else ROUND_TYPE_STATUS.get(row.round_type, app_row.status))
    # 开始时间或持续时间变化时，重算截止时间
    if "start_at" in updates or "duration_minutes" in updates:
        updates["scheduled_at"] = _deadline(
            updates.get("start_at", row.start_at),
            updates.get("duration_minutes", row.duration_minutes),
        )
    # 结果被修改时：打点最后修改时间 + 追加变化历史
    new_result = updates.get("result")
    old_result = row.result
    for key, value in updates.items():
        setattr(row, key, value)
    if "position" in updates:
        stage = db.get(StatusHistory, row.status_history_id) if row.status_history_id else None
        snapshot_updates = {"position": row.position}
        if stage and stage.position and stage.position != row.position:
            row.status_history_id = None
            snapshot_updates["status_history_id"] = None
        db.execute(update(RoundResultHistory).where(RoundResultHistory.round_id == row.id).values(**snapshot_updates))
    if new_result is not None and new_result != old_result:
        row.result_changed_at = when
        stage = _round_stage(db, row, app_row, when) if app_row else None
        _record_result(db, row, stage, old_result, when)
    db.commit()
    db.refresh(row)
    return row


def delete_round(db: Session, round_id: int) -> None:
    row = get_round(db, round_id)
    db.delete(row)
    db.commit()


def delete_status_history(db: Session, history_id: int) -> None:
    """手动删除一条状态变化记录（不影响投递当前状态）。"""
    row = db.get(StatusHistory, history_id)
    if row is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(row)
    db.commit()


def update_status_position(db: Session, history_id: int, data: StatusHistoryPositionInput) -> StatusHistory:
    row = db.get(StatusHistory, history_id)
    if row is None:
        raise HTTPException(404, "记录不存在")
    row.position = data.position
    # 用户主动补录该阶段时，同步其轮次与结果快照；不改当前岗位或其他阶段。
    for model in (InterviewRound, RoundResultHistory):
        db.execute(update(model).where(model.status_history_id == row.id).values(position=data.position))
    db.commit()
    db.refresh(row)
    return row


def delete_result_history(db: Session, history_id: int) -> None:
    """手动删除一条结果变化记录（不影响轮次当前结果）。"""
    row = db.get(RoundResultHistory, history_id)
    if row is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete(row)
    db.commit()


def list_events(db: Session) -> list[ScheduleEvent]:
    """全量自定义日程，按时间升序。"""
    stmt = select(ScheduleEvent).order_by(ScheduleEvent.event_time)
    return list(db.scalars(stmt).all())


def get_event(db: Session, event_id: int) -> ScheduleEvent:
    row = db.get(ScheduleEvent, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="日程不存在")
    return row


def create_event(db: Session, data: EventCreate) -> ScheduleEvent:
    if data.application_id is not None:
        get_application(db, data.application_id)  # 确认关联的投递存在
    row = ScheduleEvent(**data.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_event(db: Session, event_id: int, data: EventUpdate) -> ScheduleEvent:
    row = get_event(db, event_id)
    updates = data.model_dump(exclude_unset=True)
    if updates.get("application_id") is not None:
        get_application(db, updates["application_id"])
    for key, value in updates.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def delete_event(db: Session, event_id: int) -> None:
    row = get_event(db, event_id)
    db.delete(row)
    db.commit()
