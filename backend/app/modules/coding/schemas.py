"""手撕题输入约束，代码原样保存。"""
from typing import Literal
from urllib.parse import urlsplit

from pydantic import ConfigDict, Field, field_validator
from app.shared.schemas import CamelModel


class CategoryInput(CamelModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=50)

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class StatusInput(CamelModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["todo", "practicing", "mastered"] = "todo"


class ItemInput(StatusInput):
    category_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=30000)
    source_url: str = Field(default="", max_length=2000)
    language: str = Field(default="Python", min_length=1, max_length=40)
    code: str = Field(default="", max_length=100000)
    approach: str = Field(default="", max_length=30000)
    complexity: str = Field(default="", max_length=1000)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    tags: list[str] = Field(default_factory=list, max_length=12)

    @field_validator("title", "language", "source_url", mode="before")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("source_url")
    @classmethod
    def valid_url(cls, value):
        if value:
            try:
                url = urlsplit(value)
                if url.scheme not in {"http", "https"} or not url.hostname or url.username is not None or url.password is not None:
                    raise ValueError()
                _ = url.port
            except ValueError:
                raise ValueError("来源链接须为 HTTP(S) 网页地址") from None
        return value

    @field_validator("tags")
    @classmethod
    def valid_tags(cls, values):
        tags = list(dict.fromkeys(value.strip() for value in values if value.strip()))
        if any(len(value) > 40 for value in tags):
            raise ValueError("每个标签不能超过 40 个字符")
        return tags
