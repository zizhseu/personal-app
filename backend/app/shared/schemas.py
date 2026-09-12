"""共享 Pydantic 基类。"""
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """接受 camelCase 入参（也兼容 snake_case）。"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)