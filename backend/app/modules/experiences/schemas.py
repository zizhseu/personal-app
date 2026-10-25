"""采集、编辑和结构化结果契约。"""
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field

from app.shared.schemas import CamelModel


class SearchInput(CamelModel):
    keyword: str = Field(min_length=1, max_length=100)
    platform: str = Field(default="xiaohongshu", min_length=1, max_length=40)
    sort: str = Field(default="综合", min_length=1, max_length=40)
    period: str = Field(default="不限", min_length=1, max_length=40)


class SourceSelection(CamelModel):
    model_config = ConfigDict(extra="forbid")
    provider_id: str = Field(min_length=1, max_length=60)


class CollectInput(CamelModel):
    result_id: str = Field(min_length=1, max_length=100)


class ManualInput(CamelModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=60000)
    source_url: str = Field(default="", max_length=2000)


class SourceInput(CamelModel):
    id: str = Field(min_length=1, max_length=100)
    text: str = Field(max_length=60000)


class MaterialInput(CamelModel):
    revision: int = Field(ge=1)
    sources: list[SourceInput] = Field(min_length=1, max_length=32)


class WorkInput(CamelModel):
    request_id: UUID


class Question(CamelModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=500)
    source_id: str = Field(min_length=1, max_length=100)
    quote: str = Field(min_length=1, max_length=1500)
    topics: list[str] = Field(default_factory=list, max_length=6)


class Report(CamelModel):
    model_config = ConfigDict(extra="forbid")
    company: str | None = Field(default=None, max_length=100)
    position: str | None = Field(default=None, max_length=100)
    round: str | None = Field(default=None, max_length=100)
    summary: str = Field(min_length=1, max_length=2000)
    questions: list[Question] = Field(default_factory=list, max_length=60)


class ExportInput(CamelModel):
    report_id: UUID
    item_index: int = Field(ge=0, le=59)
    category_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=500)
