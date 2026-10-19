"""模型连接的输入契约与内部快照；不写入业务数据库。"""
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError


class ModelInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authMode: Literal["api_key", "chatgpt"] = "api_key"
    provider: Literal["deepseek", "openai", "custom"] = "custom"
    baseUrl: str = Field(default="https://api.deepseek.com", max_length=2048)
    model: str = Field(min_length=1, max_length=200)
    apiStyle: Literal["chat_completions", "responses"] = "chat_completions"
    apiKey: SecretStr | None = None
    clearApiKey: bool = False
    requiresApiKey: bool = True
    accountId: str | None = Field(default=None, max_length=100)


@dataclass(frozen=True)
class ModelConnection:
    auth_mode: str
    provider: str
    base_url: str
    model: str
    api_style: str = "chat_completions"
    api_key: str = field(default="", repr=False)
    requires_api_key: bool = True
    account_id: str | None = None


def parse_input(payload: dict) -> ModelInput:
    try:
        data = ModelInput.model_validate(payload)
        data.model = data.model.strip()
        if not data.model or any(ord(char) < 32 for char in data.model):
            raise ValueError("模型名称无效")
        if data.apiKey is not None:
            secret = data.apiKey.get_secret_value()
            if len(secret) > 8192 or any(ord(char) < 32 or ord(char) > 126 for char in secret):
                raise ValueError("密钥包含无效字符")
        return data
    except (ValidationError, ValueError):
        # 不回传 pydantic 的 input 字段，避免把提交的密钥带回浏览器或日志。
        raise HTTPException(400, "模型配置格式不正确，请检查模型名称、API Key 和选项") from None


def normalize_url(value: str) -> str:
    value = value.strip().rstrip("/")
    try:
        url = urlsplit(value)
        if (url.scheme not in {"https", "http"} or not url.hostname or url.username is not None
                or url.password is not None or url.query or url.fragment
                or any(char.isspace() or ord(char) < 32 for char in value)):
            raise ValueError("无效地址")
        _ = url.port
        path = url.path.rstrip("/")
        for ending in ("/chat/completions", "/responses", "/models"):
            if path.endswith(ending):
                path = path[:-len(ending)]
                break
        return urlunsplit((url.scheme.lower(), url.netloc.lower(), path, "", ""))
    except ValueError:
        raise HTTPException(400, "服务地址须为 HTTP(S) Base URL，不能含账号、密码、查询参数或片段") from None
