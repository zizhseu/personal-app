"""qa 模块 Pydantic 入参 schema。"""
from typing import Literal

from pydantic import ConfigDict

from app.modules.qa.constants import QA_STATUSES
from app.shared.schemas import CamelModel


class QaCategoryCreate(CamelModel):
    name: str


class QaCategoryUpdate(CamelModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class QaItemCreate(CamelModel):
    category_id: int
    question: str
    answer: str | None = None
    tags: list[str] | None = None  # 自定义标签（多选）
    status: Literal[QA_STATUSES] = "learning"


class QaItemUpdate(CamelModel):
    """全部字段可选，仅更新传入的字段。"""

    model_config = ConfigDict(extra="forbid")

    category_id: int | None = None
    question: str | None = None
    answer: str | None = None
    tags: list[str] | None = None
    status: Literal[QA_STATUSES] | None = None


class QaStatusPatch(CamelModel):
    status: Literal[QA_STATUSES]