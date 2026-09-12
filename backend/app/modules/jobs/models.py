"""投递记录与流程轮次模型。"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.base import Base, TimestampMixin


class Application(Base, TimestampMixin):
    """一条投递记录。"""

    __tablename__ = "application"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company: Mapped[str] = mapped_column(String(100))
    position: Mapped[str | None] = mapped_column(String(100))  # 岗位（选填）
    url: Mapped[str | None] = mapped_column(String(500))          # 招聘页面链接（点击跳转）
    apply_date: Mapped[date | None] = mapped_column(Date)         # 投递日期
    salary: Mapped[str | None] = mapped_column(String(50))        # 薪资范围（自由文本）
    base: Mapped[list[str] | None] = mapped_column(JSON)          # 意向 Base 城市（多选）
    status: Mapped[str] = mapped_column(String(20), default="screening", index=True)
    offer_decision: Mapped[str | None] = mapped_column(String(20))  # Offer 决定：accepted / rejected_offer
    note: Mapped[str | None] = mapped_column(Text)

    rounds: Mapped[list["InterviewRound"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )

    status_history: Mapped[list["StatusHistory"]] = relationship(
        cascade="all, delete-orphan",
    )

    def to_dict(self) -> dict:
        # 有时间的按时间升序在前，空时间排最后
        ordered_rounds = sorted(
            self.rounds,
            key=lambda r: (r.scheduled_at is None, r.scheduled_at or datetime.min),
        )
        ordered_history = sorted(
            self.status_history,
            key=lambda h: (h.changed_at is None, h.changed_at or datetime.min),
        )
        return {
            "id": self.id,
            "company": self.company,
            "position": self.position,
            "url": self.url,
            "applyDate": self.apply_date.isoformat() if self.apply_date else None,
            "salary": self.salary,
            "base": self.base,
            "status": self.status,
            "offerDecision": self.offer_decision,
            "note": self.note,
            "rounds": [r.to_dict() for r in ordered_rounds],
            "statusHistory": [h.to_dict() for h in ordered_history],
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class InterviewRound(Base, TimestampMixin):
    """一条投递下的流程轮次（测评/笔试/面试等）。"""

    __tablename__ = "interview_round"
    __table_args__ = (
        Index("ix_round_scheduled_at", "scheduled_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("application.id", ondelete="CASCADE"), index=True
    )
    round_type: Mapped[str] = mapped_column(String(20))
    start_at: Mapped[datetime | None] = mapped_column(DateTime)          # 开始时间
    duration_minutes: Mapped[int | None] = mapped_column(Integer)        # 持续分钟数
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime)      # 截止时间 = 开始 + 持续（后端计算）
    result: Mapped[str] = mapped_column(String(20), default="not_started")
    review_note: Mapped[str | None] = mapped_column(Text)  # 面试复盘笔记

    application: Mapped["Application"] = relationship(back_populates="rounds")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "applicationId": self.application_id,
            "roundType": self.round_type,
            "startAt": self.start_at.isoformat() if self.start_at else None,
            "durationMinutes": self.duration_minutes,
            "scheduledAt": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "result": self.result,
            "reviewNote": self.review_note,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class ScheduleEvent(Base, TimestampMixin):
    """独立自定义日程（宣讲会等，可不关联任何投递）。"""

    __tablename__ = "schedule_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))               # 日程标题
    event_type: Mapped[str] = mapped_column(String(20), default="other")
    event_time: Mapped[datetime] = mapped_column(DateTime, index=True)  # 精确到分钟
    location: Mapped[str | None] = mapped_column(String(200))     # 地点
    note: Mapped[str | None] = mapped_column(Text)                # 备注
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("application.id", ondelete="SET NULL")  # 投递删除后日程保留，仅断开关联
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "eventType": self.event_type,
            "eventTime": self.event_time.isoformat() if self.event_time else None,
            "location": self.location,
            "note": self.note,
            "applicationId": self.application_id,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }


class StatusHistory(Base, TimestampMixin):
    """投递状态变化记录（每次状态变更追加一行）。"""

    __tablename__ = "status_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("application.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[str] = mapped_column(String(20))
    changed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "applicationId": self.application_id,
            "status": self.status,
            "changedAt": self.changed_at.isoformat() if self.changed_at else None,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }