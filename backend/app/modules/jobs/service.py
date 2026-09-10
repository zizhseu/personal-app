"""jobs 模块业务逻辑。"""
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.modules.jobs.constants import ROUND_TYPE_LABELS, ROUND_TYPE_STATUS, STATUS_LABELS
from app.modules.jobs.models import Application, InterviewRound, ScheduleEvent, StatusHistory
from app.modules.jobs.schemas import (
    ApplicationCreate,
    ApplicationStatusPatch,
    ApplicationUpdate,
    EventCreate,
    EventUpdate,
    RoundCreate,
    RoundUpdate,
)


def list_applications(
    db: Session,
    status: str | None = None,
    channel: str | None = None,
    keyword: str | None = None,
) -> list[Application]:
    """全量列表（含轮次、状态历史），按投递日期倒序、空日期在后。"""
    stmt = select(Application).options(
        joinedload(Application.rounds),
        joinedload(Application.status_history),
    )
    if status:
        stmt = stmt.where(Application.status == status)
    if channel:
        stmt = stmt.where(Application.channel == channel)
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
        )
        .where(Application.id == app_id)
    )
    app_row = db.scalars(stmt).unique().first()
    if app_row is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return app_row


def _reject_stage(prev_status: str, rounds: list[InterviewRound]) -> str:
    """根据挂之前的状态推断挂在哪个阶段：
    测评前挂 → 简历挂；测评 → 测评挂；笔试 → 笔试挂；
    面试中 → 按最新的面试轮次细分（一面挂/二面挂/…），无轮次则兜底「面试挂」。
    """
    if prev_status == "assessment":
        return "assessment"
    if prev_status == "written_test":
        return "written_test"
    if prev_status == "interviewing":
        interview_types = ("first", "second", "third", "hr", "final")
        latest = max(
            (r for r in rounds if r.round_type in interview_types),
            key=lambda r: r.id,
            default=None,
        )
        return latest.round_type if latest else "interview"
    return "resume"


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
    status_changed = new_status is not None and new_status != row.status
    if status_changed:
        # 挂了 → 记录挂的阶段；离开挂了 → 清空
        if new_status == "rejected":
            updates["reject_stage"] = _reject_stage(row.status, row.rounds)
        else:
            updates["reject_stage"] = None
    for key, value in updates.items():
        setattr(row, key, value)
    if status_changed:
        row.status_history.append(StatusHistory(status=new_status))
    db.commit()
    db.refresh(row)
    return row


def patch_status(db: Session, app_id: int, data: ApplicationStatusPatch) -> Application:
    row = get_application(db, app_id)
    if row.status != data.status:
        # 挂了 → 记录挂的阶段；离开挂了 → 清空
        if data.status == "rejected":
            row.reject_stage = _reject_stage(row.status, row.rounds)
        else:
            row.reject_stage = None
        row.status = data.status
        row.status_history.append(StatusHistory(status=data.status))
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
    row = InterviewRound(
        application_id=app_id,
        start_at=start_at,
        duration_minutes=duration_minutes,
        scheduled_at=_deadline(start_at, duration_minutes),
        **payload,
    )
    db.add(row)
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
    for key, value in updates.items():
        setattr(row, key, value)
    db.commit()
    db.refresh(row)
    return row


def delete_round(db: Session, round_id: int) -> None:
    row = get_round(db, round_id)
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