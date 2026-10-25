"""共享模型调用：动态读取设置，支持兼容 API 和 ChatGPT 套餐。"""
import asyncio
import json

import httpx
from fastapi import HTTPException

from starlette.concurrency import run_in_threadpool

from app.core import config
from app.modules.settings.models import ModelConnection
from app.modules.settings.service import current_connection, ensure_ready

LLM_TIMEOUT_SECONDS = 120


def provider_error(status: int, connection: ModelConnection) -> HTTPException:
    if status in {401, 403}:
        message = "ChatGPT 授权无效或模型不可用，请在设置中重新登录并选择可用模型" if connection.auth_mode == "chatgpt" else "模型认证失败或无权使用此模型，请检查 API Key 和模型名称"
    elif status == 429:
        message = "ChatGPT 套餐或应用额度已达限制，请前往 ChatGPT 设置管理用量" if connection.auth_mode == "chatgpt" else "模型服务限流或额度不足，请检查用量后重试"
    else:
        message = "模型服务返回错误，请检查模型名称、接口格式和服务地址"
    return HTTPException(502, f"{message}（HTTP {status}）")


async def bearer_token(connection: ModelConnection) -> str:
    if connection.auth_mode == "chatgpt":
        from app.modules.settings import chatgpt

        return await run_in_threadpool(chatgpt.access_token, connection.account_id)
    return connection.api_key if connection.requires_api_key else ""


async def responses_text(client: httpx.AsyncClient, connection: ModelConnection, headers: dict, messages: list[dict]) -> str:
    # ChatGPT 套餐只支持 Responses 流式接口，不发送 temperature 或服务端会话参数。
    inputs = [{"role": "developer" if message["role"] == "system" else message["role"],
               "content": message["content"]} for message in messages]
    async with client.stream("POST", f"{connection.base_url}/responses", headers=headers,
                             json={"model": connection.model, "input": inputs, "store": False, "stream": True}) as response:
        if response.status_code != 200:
            raise provider_error(response.status_code, connection)
        deltas: list[str] = []
        data: list[str] = []
        received = 0
        async for line in response.aiter_lines():
            received += len(line)
            if received > 4_000_000:
                raise HTTPException(502, "模型回复过长，请缩小生成范围后重试")
            if line.startswith("data:"):
                data.append(line[5:].lstrip())
                continue
            if line or not data:
                continue
            raw = "\n".join(data)
            data.clear()
            if raw == "[DONE]":
                break
            try:
                event = json.loads(raw)
                kind = event.get("type")
                if kind == "response.output_text.delta" and isinstance(event.get("delta"), str):
                    deltas.append(event["delta"])
                elif kind in {"response.failed", "response.incomplete", "error"}:
                    raise HTTPException(502, "模型未能完成生成，请检查模型权限或额度后重试")
                elif kind == "response.completed":
                    completed = event["response"]
                    if completed.get("status") != "completed":
                        raise ValueError()
                    output = completed.get("output", [])
                    text = "".join(part["text"] for item in output if item.get("type") == "message"
                                   for part in item.get("content", []) if part.get("type") == "output_text")
                    text = text or "".join(deltas)
                    if not isinstance(text, str) or not text.strip():
                        raise ValueError()
                    return text
            except (ValueError, KeyError, TypeError, AttributeError):
                raise HTTPException(502, "模型服务返回了无法识别的回复，请稍后重试") from None
    # 收到部分文字不能代表成功；只有明确的 completed 事件才提交面试结果。
    raise HTTPException(502, "模型回复中途断开，记录已保留，请重试生成")


async def llm_chat(messages: list[dict], *, connection: ModelConnection | None = None) -> str:
    connection = connection or current_connection()
    ensure_ready(connection)
    try:
        async with asyncio.timeout(LLM_TIMEOUT_SECONDS):
            token = await bearer_token(connection)
            headers = {"Authorization": f"Bearer {token}"} if token else {}
            async with httpx.AsyncClient(timeout=httpx.Timeout(LLM_TIMEOUT_SECONDS, connect=10), follow_redirects=False) as client:
                if connection.api_style == "responses":
                    return await responses_text(client, connection, headers, messages)
                payload = {"model": connection.model, "messages": messages}
                if connection.provider != "openai":
                    payload["temperature"] = config.LLM_TEMPERATURE
                response = await client.post(f"{connection.base_url}/chat/completions", headers=headers, json=payload)
    except (TimeoutError, httpx.TimeoutException):
        raise HTTPException(504, "模型响应超时，请稍后重试或调整模型服务配置") from None
    except httpx.RequestError:
        raise HTTPException(502, "无法连接模型服务，请检查服务地址和网络连接") from None
    if response.status_code != 200:
        raise provider_error(response.status_code, connection)
    try:
        content = response.json()["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError()
    except (ValueError, KeyError, IndexError, TypeError):
        raise HTTPException(502, "模型服务返回了无法识别的回复，请稍后重试") from None
    return content


async def list_models(connection: ModelConnection) -> list[dict]:
    # 获取目录不要求已选择模型；目录成功也不代表该模型能完成一次推理。
    if connection.auth_mode == "api_key" and connection.requires_api_key and not connection.api_key:
        raise HTTPException(400, "请先填写 API Key，或选择无需密钥的本地服务")
    try:
        async with asyncio.timeout(30):
            token = await bearer_token(connection)
            async with httpx.AsyncClient(timeout=httpx.Timeout(25, connect=10), follow_redirects=False) as client:
                response = await client.get(f"{connection.base_url}/models", headers={"Authorization": f"Bearer {token}"} if token else {})
        if response.status_code != 200:
            raise provider_error(response.status_code, connection)
        body = response.json()
        if connection.auth_mode == "chatgpt":
            models = [{"id": row["slug"], "name": row.get("display_name", row["slug"])}
                      for row in body["models"] if row.get("visibility") == "list"]
        else:
            models = [{"id": row["id"], "name": row["id"]} for row in body["data"]]
        if not all(isinstance(row["id"], str) and row["id"] and isinstance(row["name"], str) for row in models):
            raise ValueError()
        return models[:500]
    except (TimeoutError, httpx.TimeoutException):
        raise HTTPException(504, "获取模型列表超时，可手动填写模型名称") from None
    except httpx.RequestError:
        raise HTTPException(502, "无法获取模型列表，请检查服务地址或手动填写模型名称") from None
    except (ValueError, KeyError, TypeError, AttributeError):
        raise HTTPException(502, "服务没有返回兼容的模型列表，可手动填写模型名称") from None
