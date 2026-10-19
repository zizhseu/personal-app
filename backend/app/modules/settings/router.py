"""模型设置接口：只允许本机访问，公开响应不含原始凭据。"""
import ipaddress
import time
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.modules.settings import chatgpt, service
from app.modules.settings.models import parse_input


def local_only(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    try:
        if not request.client or not ipaddress.ip_address(request.client.host).is_loopback:
            raise ValueError()
        if request.url.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError()
        origin = request.headers.get("origin")
        if origin and urlsplit(origin).hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError()
        if request.headers.get("sec-fetch-site") == "cross-site":
            raise ValueError()
    except ValueError:
        raise HTTPException(403, "模型与账号设置仅允许从本机应用访问") from None


router = APIRouter(prefix="/api/settings", tags=["设置"], dependencies=[Depends(local_only)])


@router.get("/model")
def read_model_settings():
    return service.public_settings()


@router.put("/model")
def update_model_settings(payload: dict):
    return service.save_settings(parse_input(payload))


@router.post("/model/test")
async def test_model(payload: dict):
    from app.modules.aitools.service import llm_chat

    connection = service.draft_connection(parse_input(payload))
    started = time.monotonic()
    await llm_chat([{"role": "user", "content": "请只回复：连接成功"}], connection=connection)
    return {"ok": True, "model": connection.model, "latencyMs": round((time.monotonic() - started) * 1000)}


@router.post("/model/models")
async def models(payload: dict):
    from app.modules.aitools.service import list_models

    data = parse_input({**payload, "model": payload.get("model") or "model-picker"})
    return {"models": await list_models(service.draft_connection(data))}


@router.get("/chatgpt")
def read_chatgpt_accounts():
    return chatgpt.public_accounts()


@router.post("/chatgpt/login")
def login(payload: dict):
    account_id = payload.get("accountId")
    if account_id is not None and not isinstance(account_id, str):
        raise HTTPException(400, "账号连接编号格式不正确")
    return chatgpt.start_login(account_id)


@router.get("/chatgpt/login/{attempt_id}")
def login_result(attempt_id: str):
    return chatgpt.login_status(attempt_id)


@router.delete("/chatgpt/login/{attempt_id}")
def cancel_login(attempt_id: str):
    chatgpt.cancel_login(attempt_id)
    return {"ok": True}


@router.put("/chatgpt/active")
def choose_account(payload: dict):
    account_id = payload.get("accountId")
    if not isinstance(account_id, str):
        raise HTTPException(400, "请选择账号连接")
    return chatgpt.select_account(account_id)


@router.post("/chatgpt/{account_id}/welcome")
def acknowledge_welcome(account_id: str):
    chatgpt.acknowledge_welcome(account_id)
    return {"ok": True}


@router.delete("/chatgpt/{account_id}")
def disconnect(account_id: str):
    return chatgpt.disconnect(account_id)
