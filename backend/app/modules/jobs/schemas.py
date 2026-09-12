"""Pydantic 入参 schema（camelCase 别名，与前端字段命名一致）。"""
from datetime import date, datetime
from typing import Literal

from pydantic import ConfigDict

from app.modules.jobs.constants import APPLICATION_STATUSES, EVENT_TYPES, ROUND_RESULTS, ROUND_TYPES
from app.shared.schemas import CamelModel


class ApplicationCreate(CamelModel):
    company: str
    position: str | None = None
    url: str | None = None
    apply_date: date | None = None
    salary: str | None = None
    base: list[str] | None = None  # 意向 Base 城市（多选）
    status: Literal[APPLICATION_STATUSES] = "screening"
    note: str | None = None


class ApplicationUpdate(CamelModel):
    """全部字段可选，仅更新传入的字段。"""

    model_config = ConfigDict(extra="forbid")

    company: str | None = None
    position: str | None = None
    url: str | None = None
    apply_date: date | None = None
    salary: str | None = None
    base: list[str] | None = None
    status: Literal[APPLICATION_STATUSES] | None = None
    note: str | None = None


class ApplicationStatusPatch(CamelModel):
    status: Literal[APPLICATION_STATUSES]


class OfferDecisionPatch(CamelModel):
    """Offer 决定（仅状态为 Offer 时可设置）。"""

    offer_decision: Literal["accepted", "rejected_offer"]


class RoundCreate(CamelModel):
    round_type: Literal[ROUND_TYPES]
    start_at: datetime | None = None      # 开始时间
    duration_minutes: int | None = None   # 持续分钟数（截止时间 = 开始 + 持续，后端计算）
    result: Literal[ROUND_RESULTS] = "not_started"
    review_note: str | None = None


class RoundUpdate(CamelModel):
    model_config = ConfigDict(extra="forbid")

    round_type: Literal[ROUND_TYPES] | None = None
    start_at: datetime | None = None
    duration_minutes: int | None = None
    result: Literal[ROUND_RESULTS] | None = None
    review_note: str | None = None


class EventCreate(CamelModel):
    title: str
    event_type: Literal[EVENT_TYPES] = "other"
    event_time: datetime  # 精确到分钟，秒由前端固定为 00
    location: str | None = None
    note: str | None = None
    application_id: int | None = None  # 可选关联的投递


class EventUpdate(CamelModel):
    """全部字段可选，仅更新传入的字段。"""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    event_type: Literal[EVENT_TYPES] | None = None
    event_time: datetime | None = None
    location: str | None = None
    note: str | None = None
    application_id: int | None = None