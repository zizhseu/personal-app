"""quiz 模块 Pydantic 入参 schema。"""
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StrictInt, StringConstraints, field_validator, model_validator

from app.shared.schemas import CamelModel


class QuizCategoryCreate(CamelModel):
    name: str


class QuizCategoryUpdate(CamelModel):
    model_config = ConfigDict(extra="forbid")

    name: str


QuestionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def validate_answer_indices(answer: list[int], options_count: int, qtype: str) -> list[int]:
    """预览、新增和编辑共用的答案约束，不推测或补写正确答案。"""
    clean = sorted(set(answer))
    if any(index < 0 or index >= options_count for index in clean):
        raise ValueError("答案下标超出选项范围")
    if qtype == "single" and len(clean) != 1:
        raise ValueError("单选题答案必须恰好 1 个选项")
    if qtype == "multi" and len(clean) < 2:
        raise ValueError("多选题答案至少 2 个选项")
    return clean


class QuizQuestion(CamelModel):
    """已校验的题目内容，AI 预览与实际入库使用同一份契约。"""

    question: QuestionText
    options: list[QuestionText] = Field(min_length=2, max_length=8)
    answer: list[StrictInt] = Field(min_length=1)
    qtype: Literal["single", "multi"] = "single"
    analysis: str | None = None

    @model_validator(mode="after")
    def validate_answers(self):
        self.answer = validate_answer_indices(self.answer, len(self.options), self.qtype)
        return self


class QuizItemCreate(QuizQuestion):
    category_id: int


class QuizParseResult(CamelModel):
    questions: list[QuizQuestion]


class QuizItemUpdate(CamelModel):
    """全部字段可选，仅更新传入的字段。"""

    model_config = ConfigDict(extra="forbid")

    category_id: int | None = None
    question: QuestionText | None = None
    options: list[QuestionText] | None = Field(default=None, min_length=2, max_length=8)
    answer: list[StrictInt] | None = Field(default=None, min_length=1)
    qtype: Literal["single", "multi"] | None = None
    analysis: str | None = None

    @field_validator("category_id", "question", "options", "answer", "qtype", mode="before")
    @classmethod
    def reject_null_fields(cls, value):
        if value is None:
            raise ValueError("该字段不能设为空值")
        return value


class QuizParseRequest(CamelModel):
    """AI 解析导入：原始文本。"""

    text: str
