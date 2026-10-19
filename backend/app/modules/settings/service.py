"""动态模型设置，界面设置优先于 .env，清除密钥后不会自动恢复旧密钥。"""
from fastapi import HTTPException

from app.core import config, private_store
from app.modules.settings.models import ModelConnection, ModelInput, normalize_url

SETTINGS_FILE = "model-settings.private"


def api_connection(document: dict | None = None) -> ModelConnection:
    document = private_store.read_document(SETTINGS_FILE) if document is None else document
    saved = document.get("api")
    if saved is not None:
        return ModelConnection(
            auth_mode="api_key", provider=saved["provider"], base_url=saved["base_url"],
            model=saved["model"], api_style=saved["api_style"],
            api_key=saved.get("api_key", ""), requires_api_key=saved.get("requires_api_key", True),
        )
    base_url = normalize_url(config.LLM_BASE_URL)
    provider = "openai" if base_url == "https://api.openai.com/v1" else "custom"
    if base_url in {"https://api.deepseek.com", "https://api.deepseek.com/v1"}:
        provider = "deepseek"
    return ModelConnection(
        auth_mode="api_key", provider=provider, base_url=base_url, model=config.LLM_MODEL,
        api_style=config.LLM_API_STYLE, api_key=config.LLM_API_KEY,
    )


def draft_connection(data: ModelInput) -> ModelConnection:
    if data.authMode == "chatgpt":
        return ModelConnection("chatgpt", "openai", "https://api.openai.com/v1", data.model, "responses", account_id=data.accountId)
    base_url = normalize_url(data.baseUrl)
    previous = api_connection()
    secret = ""
    if not data.clearApiKey:
        if data.apiKey is not None and data.apiKey.get_secret_value().strip():
            secret = data.apiKey.get_secret_value().strip()
        elif previous.base_url == base_url and previous.provider == data.provider:
            secret = previous.api_key
    # 改变地址或供应商时，空白输入不会把旧连接的密钥发送到新服务。
    return ModelConnection("api_key", data.provider, base_url, data.model, data.apiStyle, secret, data.requiresApiKey)


def current_connection() -> ModelConnection:
    document = private_store.read_document(SETTINGS_FILE)
    if document.get("auth_mode") == "chatgpt":
        return ModelConnection("chatgpt", "openai", "https://api.openai.com/v1", document.get("chatgpt_model", ""),
                               "responses", account_id=document.get("chatgpt_account_id"))
    return api_connection(document)


def ensure_ready(connection: ModelConnection) -> None:
    if not connection.model:
        raise HTTPException(400, "请在设置中选择或填写模型名称")
    if connection.auth_mode == "chatgpt":
        from app.modules.settings import chatgpt

        chatgpt.require_account(connection.account_id)
    elif connection.requires_api_key and not connection.api_key:
        raise HTTPException(400, "尚未配置 API Key，请前往设置中的「大模型」填写并保存")


def is_ready(connection: ModelConnection | None = None) -> bool:
    try:
        ensure_ready(connection or current_connection())
        return True
    except HTTPException as error:
        if error.status_code >= 500:
            raise
        return False


def public_settings() -> dict:
    from app.modules.settings import chatgpt

    document = private_store.read_document(SETTINGS_FILE)
    connection = current_connection()
    api = api_connection(document)
    return {
        "authMode": connection.auth_mode, "model": connection.model, "llmReady": is_ready(connection),
        "source": "saved" if document else "environment",
        "api": {"provider": api.provider, "baseUrl": api.base_url, "model": api.model,
                "apiStyle": api.api_style, "requiresApiKey": api.requires_api_key,
                "apiKeyConfigured": bool(api.api_key)},
        "chatgptModel": document.get("chatgpt_model", ""), "chatgptAccountId": document.get("chatgpt_account_id"),
        "chatgpt": chatgpt.public_accounts(),
    }


def save_settings(data: ModelInput) -> dict:
    with private_store.LOCK:
        connection = draft_connection(data)
        document = private_store.read_document(SETTINGS_FILE)
        document["auth_mode"] = data.authMode
        if data.authMode == "chatgpt":
            ensure_ready(connection)
            document["chatgpt_model"] = connection.model
            from app.modules.settings import chatgpt

            document["chatgpt_account_id"] = chatgpt.require_account(connection.account_id)["id"]
        else:
            document["api"] = {
                "provider": connection.provider, "base_url": connection.base_url, "model": connection.model,
                "api_style": connection.api_style, "api_key": connection.api_key,
                "requires_api_key": connection.requires_api_key,
            }
        private_store.write_document(SETTINGS_FILE, document)
    return public_settings()
