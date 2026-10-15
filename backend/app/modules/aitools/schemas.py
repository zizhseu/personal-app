"""aitools 模块 Pydantic 入参 schema。"""
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StrictInt, StringConstraints, model_validator

from app.shared.schemas import CamelModel


NonemptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class ResumeInput(CamelModel):
    model_config = ConfigDict(extra="forbid")
    name: NonemptyText = Field(max_length=100)
    content: NonemptyText = Field(max_length=30000)

class InterviewCreate(CamelModel):
    model_config = ConfigDict(extra="forbid")
    resume_id: int = Field(gt=0)
    target_role: str = Field(default="", max_length=100)
    focus: str = Field(default="", max_length=500)


class OperationRequest(CamelModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID


class AnswerRequest(OperationRequest):
    content: NonemptyText = Field(max_length=6000)


class ReviewItem(CamelModel):
    model_config = ConfigDict(extra="forbid")
    question_message_id: StrictInt = Field(gt=0)
    answer_message_id: StrictInt = Field(gt=0)
    resume_quote: str = Field(default="", max_length=2000)
    assessment: Literal["solid", "partial", "needs_work"]
    feedback: NonemptyText = Field(max_length=2000)
    improvement_guide: NonemptyText = Field(max_length=4000)
    knowledge_points: list[NonemptyText] = Field(default_factory=list, max_length=10)


class InterviewReport(CamelModel):
    model_config = ConfigDict(extra="forbid")
    summary: NonemptyText = Field(max_length=2000)
    strengths: list[NonemptyText] = Field(default_factory=list, max_length=10)
    improvements: list[NonemptyText] = Field(default_factory=list, max_length=10)
    items: list[ReviewItem] = Field(min_length=1, max_length=30)


class ReviewActionInput(CamelModel):
    model_config = ConfigDict(extra="forbid")
    item_index: int = Field(ge=0)
    kind: Literal["qa", "todo"]
    category_id: int = Field(gt=0)
    title: NonemptyText = Field(max_length=500)
    content: str = Field(default="", max_length=20000)
    due_at: datetime | None = None

    @model_validator(mode="after")
    def validate_todo_limits(self):
        if self.kind == "todo" and (len(self.title) > 200 or len(self.content) > 10000):
            raise ValueError("待办标题不能超过 200 字，备注不能超过 10000 字")
        return self


class TtsRequest(CamelModel):
    text: str
