"""aitools 模块 Pydantic 入参 schema。"""
from typing import Literal

from pydantic import ConfigDict, Field

from app.shared.schemas import CamelModel


class ChatMessage(CamelModel):
    role: Literal["user", "assistant"]
    content: str


class InterviewChatRequest(CamelModel):
    """AI 面试对话请求：前端维护对话历史，后端组装面试官 prompt 并调用 LLM。"""

    questionIds: list[int] = Field(default_factory=list)  # 本轮面试的题目（来自八股库）
    history: list[ChatMessage] = Field(default_factory=list)
    message: str


class TtsRequest(CamelModel):
    text: str