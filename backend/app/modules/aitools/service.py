"""共享的 OpenAI 兼容模型调用，供面试和题目解析使用。"""
import asyncio

import httpx
from fastapi import HTTPException

from app.core.config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_TEMPERATURE

LLM_TIMEOUT_SECONDS = 120


async def llm_chat(messages: list[dict]) -> str:
    """调用 OpenAI 兼容接口（DeepSeek/GLM/任意兼容服务）。"""
    if not LLM_API_KEY:
        raise HTTPException(
            status_code=400,
            detail="尚未配置大模型 API Key：请在 backend/.env 中设置 LLM_API_KEY（DeepSeek / 智谱等 OpenAI 兼容服务）后重启",
        )
    try:
        # 同时限制连接等待、读取等待和整次调用，前端 AI 请求预留额外处理时间。
        async with asyncio.timeout(LLM_TIMEOUT_SECONDS):
            async with httpx.AsyncClient(timeout=httpx.Timeout(LLM_TIMEOUT_SECONDS, connect=10)) as client:
                resp = await client.post(
                    f"{LLM_BASE_URL.rstrip('/')}/chat/completions",
                    headers={"Authorization": f"Bearer {LLM_API_KEY}"},
                    json={
                        "model": LLM_MODEL,
                        "messages": messages,
                        "temperature": LLM_TEMPERATURE,
                    },
                )
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise HTTPException(status_code=504, detail="模型响应超时，请稍后重试或调整模型服务配置") from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail="无法连接模型服务，请检查服务地址和网络连接") from exc

    if resp.status_code != 200:
        # 不向浏览器直接回传上游调试正文，避免夹带服务端配置或凭据。
        raise HTTPException(status_code=502, detail=f"模型服务返回错误（HTTP {resp.status_code}），请检查配置或稍后重试")
    try:
        content = resp.json()["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("模型回复为空或不是文本")
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise HTTPException(status_code=502, detail="模型服务返回了无法识别的回复，请稍后重试") from exc
    return content
