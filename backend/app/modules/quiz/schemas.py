"""quiz 模块 Pydantic 入参 schema。"""
from typing import Literal

from pydantic import ConfigDict, Field

from app.shared.schemas import CamelModel


class QuizCategoryCreate(CamelModel):
    name: str


class QuizCategoryUpdate(CamelModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class QuizItemCreate(CamelModel):
    category_id: int
    question: str
    options: list[str] = Field(min_length=2, max_length=8)
    answer: list[int] = Field(min_length=1)
    qtype: Literal["single", "multi"] = "single"
    analysis: str | None = None


class QuizItemUpdate(CamelModel):
    """全部字段可选，仅更新传入的字段。"""

    model_config = ConfigDict(extra="forbid")

    category_id: int | None = None
    question: str | None = None
    options: list[str] | None = Field(default=None, min_length=2, max_length=8)
    answer: list[int] | None = Field(default=None, min_length=1)
    qtype: Literal["single", "multi"] | None = None
    analysis: str | None = None


class QuizParseRequest(CamelModel):
    """AI 解析导入：原始文本。"""

    text: str