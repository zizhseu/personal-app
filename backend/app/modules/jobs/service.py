"""jobs 模块业务逻辑。"""
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
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
    RoundCreate,
    RoundUpdate,
)


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
    return list(db.scalars(stmt).unique().all())


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


def _sync_rounds_on_status_change(
    db: Session, row: Application, old_status: str, new_status: str
) -> None:
    """状态正向推进时，把当前最新轮次置为「通过」（进入了下一环节 = 上一环节通过）。
    边界：倒退/平移不联动；「未通过」是用户录入的事实不覆盖；无轮次静默跳过。
    下一环节的新轮次默认「未开始」（前后端默认值），无需在此处理。
    """
    if old_status not in STATUS_FLOW or new_status not in STATUS_FLOW:
        return
    if STATUS_FLOW.index(new_status) <= STATUS_FLOW.index(old_status):
        return
    if row.rounds:
        latest = max(row.rounds, key=lambda r: r.id)
        if latest.result in ("not_started", "completed", "not_attended"):
            old = latest.result
            latest.result = "passed"
            db.add(
                RoundResultHistory(
                    round_id=latest.id,
                    application_id=row.id,
                    status=new_status,  # 联动发生时状态正在推进，归属新状态
                    from_result=old,
                    to_result="passed",
                )
            )


def create_application(db: Session, data: ApplicationCreate) -> Application:
    row = Application(**data.model_dump())
    # 初始状态也记一条历史（如：投递中 → 2026-09-10 15:30）
    row.status_history.append(StatusHistory(status=row.status))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_application(db: Session, app_id: int, data: ApplicationUpdate) -> Application:
    row = get_application(db, app_id)
    updates = data.model_dump(exclude_unset=True)
    new_status = updates.get("status")
    old_status = row.status  # 先取旧状态（setattr 会覆盖）
    for key, value in updates.items():
        setattr(row, key, value)
    if new_status is not None and new_status != old_status:
        _sync_rounds_on_status_change(db, row, old_status, new_status)
        row.status_history.append(StatusHistory(status=new_status))
    db.commit()
    db.refresh(row)
    return row


def patch_status(db: Session, app_id: int, data: ApplicationStatusPatch) -> Application:
    row = get_application(db, app_id)
    if row.status != data.status:
        _sync_rounds_on_status_change(db, row, row.status, data.status)
        row.status = data.status
        row.status_history.append(StatusHistory(status=data.status))
        db.commit()
        db.refresh(row)
    return row


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


def _deadline(
    start_at: datetime | None, duration_minutes: int | None
) -> datetime | None:
    """截止时间 = 开始时间 + 持续时间；无开始时间则无截止。"""
    if start_at is None:
        return None
    return start_at + timedelta(minutes=duration_minutes or 0)


def _check_round_type_status(round_type: str, app_status: str) -> None:
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
    _check_round_type_status(data.round_type, app_row.status)
    payload = data.model_dump()
    start_at = payload.pop("start_at")
    duration_minutes = payload.pop("duration_minutes")
    # 创建时若结果已不再是「未开始」，记录结果变更时间
    result_changed_at = datetime.now() if payload.get("result", "not_started") != "not_started" else None
    row = InterviewRound(
        application_id=app_id,
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
        db.add(
            RoundResultHistory(
                round_id=row.id,
                application_id=app_id,
                status=app_row.status,
                from_result=None,
                to_result=row.result,
            )
        )
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
    if app_row is not None:
        _check_round_type_status(new_type, app_row.status)
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
    if new_result is not None and new_result != old_result:
        row.result_changed_at = datetime.now()
        db.add(
            RoundResultHistory(
                round_id=row.id,
                application_id=row.application_id,
                status=app_row.status if app_row is not None else "",
                from_result=old_result,
                to_result=new_result,
            )
        )
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