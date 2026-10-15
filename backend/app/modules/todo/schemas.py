"""待办目录与事项输入校验。"""
from typing import Annotated
from datetime import datetime

from pydantic import ConfigDict, Field, StringConstraints, field_validator

from app.shared.schemas import CamelModel


class CategoryInput(CamelModel):
    model_config = ConfigDict(extra="forbid")
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]


TodoTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class TodoFields(CamelModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=10000)
    due_at: datetime | None = None

    @field_validator("due_at")
    @classmethod
    def local_datetime(cls, value: datetime | None) -> datetime | None:
        # 与应用其他时间字段保持一致：按服务端本地时间存储。
        if value is not None and value.tzinfo is not None:
            return value.astimezone().replace(tzinfo=None)
        return value


class TodoItemCreate(TodoFields):
    category_id: int = Field(gt=0)
    title: TodoTitle


class TodoItemUpdate(TodoFields):
    title: TodoTitle | None = None
    completed: bool | None = None

    @field_validator("title", "completed")
    @classmethod
    def reject_null(cls, value):
        # 省略字段表示不修改；只有备注与截止时间允许显式清空。
        if value is None:
            raise ValueError("该字段不能为 null")
        return value
