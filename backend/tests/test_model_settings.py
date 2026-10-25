"""模型设置与官方 OAuth 的行为回归；只使用临时目录和模拟上游。"""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import time
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, HTTPException
import httpx
import jwt

from app.core import config, private_store
from app.modules.aitools import service as llm
from app.modules.settings import chatgpt, service
from app.modules.settings.models import normalize_url, parse_input
from app.modules.settings.router import router

ORIGINAL_ASYNC_CLIENT = httpx.AsyncClient
ORIGINAL_CLIENT = httpx.Client


class SettingsFixture:
    def setUp(self):
        self.directory = TemporaryDirectory(prefix="personal-model-tests-")
        self.patches = [patch.object(config, "DATA_DIR", Path(self.directory.name)),
                        patch.object(config, "LLM_API_KEY", "environment-test-key"),
                        patch.object(config, "LLM_BASE_URL", "https://example.invalid/v1"),
                        patch.object(config, "LLM_MODEL", "environment-model"),
                        patch.object(config, "LLM_API_STYLE", "chat_completions")]
        for item in self.patches:
            item.start()
        self.addCleanup(self.directory.cleanup)
        for item in self.patches:
            self.addCleanup(item.stop)

    def input(self, **changes):
        return parse_input({"authMode": "api_key", "provider": "custom", "baseUrl": "https://example.invalid/v1",
                            "model": "saved-model", **changes})

    def account(self, **changes):
        account = {"id": "account-one", "label": "测试连接 1", "email": "test@example.invalid", "subject": "subject-one",
                   "client_id": "oaiapp_test_client", "access_token": "synthetic-access", "refresh_token": "synthetic-refresh",
                   "id_token": "synthetic-id", "expires_at": time.time() + 3600, "scopes": [chatgpt.PLAN_SCOPE], **changes}
        private_store.write_document(chatgpt.ACCOUNTS_FILE, {"host_id": "urn:uuid:test-host", "active_id": account["id"], "accounts": [account]})
        return account


class ModelSettingsTests(SettingsFixture, unittest.TestCase):
    def test_environment_fallback_is_private_and_does_not_create_files(self):
        settings = service.public_settings()
        self.assertTrue(settings["llmReady"])
        self.assertEqual(settings["source"], "environment")
        self.assertTrue(settings["api"]["apiKeyConfigured"])
        self.assertNotIn("environment-test-key", json.dumps(settings))
        self.assertEqual(list(Path(self.directory.name).iterdir()), [])

    def test_save_keep_rotate_clear_and_reopen_do_not_restore_environment_key(self):
        service.save_settings(self.input(apiKey="saved-secret"))
        self.assertEqual(service.current_connection().api_key, "saved-secret")
        service.save_settings(self.input(model="changed-model"))
        self.assertEqual(service.current_connection().api_key, "saved-secret")
        service.save_settings(self.input(apiKey="replacement-secret"))
        self.assertEqual(service.current_connection().api_key, "replacement-secret")
        result = service.save_settings(self.input(clearApiKey=True))
        self.assertFalse(result["llmReady"])
        self.assertFalse(result["api"]["apiKeyConfigured"])
        service.save_settings(self.input())
        self.assertEqual(service.current_connection().api_key, "")

    def test_changing_provider_or_url_never_reuses_a_saved_key(self):
        service.save_settings(self.input(apiKey="old-service-key"))
        for changes in ({"baseUrl": "https://another.invalid/v1"}, {"provider": "openai"}, {"baseUrl": "https://example.invalid/other"}):
            self.assertEqual(service.draft_connection(self.input(**changes)).api_key, "")
        service.save_settings(self.input(baseUrl="https://another.invalid/v1"))
        self.assertEqual(service.current_connection().api_key, "")

    def test_normalization_handles_full_endpoint_and_preserves_api_prefix(self):
        for value in ("https://example.invalid/v1/", "https://example.invalid/v1/chat/completions", "https://example.invalid/v1/responses"):
            self.assertEqual(normalize_url(value), "https://example.invalid/v1")
            self.assertEqual(service.draft_connection(self.input(baseUrl=value)).api_key, "environment-test-key")
        self.assertEqual(normalize_url("http://127.0.0.1:8811/api/v1"), "http://127.0.0.1:8811/api/v1")

    def test_invalid_url_and_key_errors_never_echo_submitted_credentials(self):
        for value in ("ftp://example.invalid", "https://user:private-key@example.invalid/v1", "https://example.invalid/v1?api_key=private-key", "https://example.invalid/#secret", "https://example.invalid:bad", "https://example.invalid/a b"):
            with self.subTest(value=value), self.assertRaises(HTTPException) as caught:
                normalize_url(value)
            self.assertNotIn("private-key", caught.exception.detail)
        for value in ("secret\nvalue", "密钥", "a" * 8193):
            with self.assertRaises(HTTPException) as caught:
                self.input(apiKey=value)
            self.assertNotIn(value, caught.exception.detail)

    def test_private_file_roundtrip_and_failed_replace_keep_previous_settings(self):
        service.save_settings(self.input(apiKey="private-file-secret"))
        path = Path(self.directory.name) / service.SETTINGS_FILE
        if os.name == "nt":
            self.assertNotIn(b"private-file-secret", path.read_bytes())
        else:
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with patch.object(private_store.os, "replace", side_effect=OSError("fake-write-failure")):
            with self.assertRaises(HTTPException):
                service.save_settings(self.input(apiKey="new-secret"))
        self.assertEqual(service.current_connection().api_key, "private-file-secret")
        self.assertFalse(list(Path(self.directory.name).glob(".private-*")))

    def test_local_service_without_key_and_existing_api_settings_survive_account_mode(self):
        service.save_settings(self.input(apiKey="", clearApiKey=True, requiresApiKey=False))
        self.assertTrue(service.is_ready())
        self.account()
        service.save_settings(self.input(authMode="chatgpt", model="account-model", accountId="account-one"))
        self.assertEqual(service.current_connection().auth_mode, "chatgpt")
        self.assertEqual(service.current_connection().account_id, "account-one")
        self.assertEqual(service.api_connection().api_key, "")
        self.assertFalse(service.api_connection().requires_api_key)

    def test_ungranted_chatgpt_plan_cannot_be_saved_as_active_connection(self):
        self.account(scopes=["openid", "email"])
        with self.assertRaises(HTTPException) as caught:
            service.save_settings(self.input(authMode="chatgpt", model="account-model"))
        self.assertEqual(caught.exception.status_code, 403)
        self.assertEqual(service.current_connection().auth_mode, "api_key")

    def test_selecting_another_account_does_not_switch_saved_ai_connection(self):
        self.account()
        service.save_settings(self.input(authMode="chatgpt", model="account-model", accountId="account-one"))
        document = private_store.read_document(chatgpt.ACCOUNTS_FILE)
        document["accounts"].append({**document["accounts"][0], "id": "account-two", "subject": "subject-two", "client_id": "oaiapp_two"})
        private_store.write_document(chatgpt.ACCOUNTS_FILE, document)
        chatgpt.select_account("account-two")
        self.assertEqual(service.current_connection().account_id, "account-one")


class ModelApiTests(SettingsFixture, unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.app = FastAPI()
        self.app.include_router(router)
        self.client = ORIGINAL_ASYNC_CLIENT(transport=httpx.ASGITransport(app=self.app), base_url="http://127.0.0.1")

    async def asyncTearDown(self):
        await self.client.aclose()

    def mock_models(self, handler):
        return patch.object(llm.httpx, "AsyncClient", side_effect=lambda **kwargs: ORIGINAL_ASYNC_CLIENT(
            transport=httpx.MockTransport(handler), trust_env=False, **kwargs))

    async def test_api_save_read_and_validation_never_return_secret(self):
        response = await self.client.put("/api/settings/model", json={"model": "model-a", "provider": "custom", "baseUrl": "https://example.invalid/v1", "apiKey": "api-submitted-secret"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("api-submitted-secret", response.text)
        read = await self.client.get("/api/settings/model")
        self.assertNotIn("api-submitted-secret", read.text)
        self.assertEqual(read.headers["cache-control"], "no-store")
        invalid = await self.client.put("/api/settings/model", json={"model": "", "apiKey": "api-submitted-secret"})
        self.assertEqual(invalid.status_code, 400)
        self.assertNotIn("api-submitted-secret", invalid.text)

    async def test_foreign_origin_and_rebinding_host_are_rejected(self):
        for headers in ({"Origin": "https://evil.invalid"}, {"Host": "evil.invalid"}, {"Sec-Fetch-Site": "cross-site"}):
            response = await self.client.get("/api/settings/model", headers=headers)
            self.assertEqual(response.status_code, 403)

    async def test_connection_test_uses_unsaved_draft_and_fixed_text_without_saving(self):
        captured = []
        def handler(request):
            captured.append(request)
            return httpx.Response(200, json={"choices": [{"message": {"content": "连接成功"}}]})
        with self.mock_models(handler):
            response = await self.client.post("/api/settings/model/test", json={"provider": "custom", "baseUrl": "https://draft.invalid/v1", "model": "draft-model", "apiKey": "draft-only-key"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(captured[0].url), "https://draft.invalid/v1/chat/completions")
        self.assertEqual(captured[0].headers["authorization"], "Bearer draft-only-key")
        self.assertEqual(json.loads(captured[0].content)["messages"], [{"role": "user", "content": "请只回复：连接成功"}])
        self.assertEqual(service.current_connection().model, "environment-model")
        self.assertFalse((Path(self.directory.name) / service.SETTINGS_FILE).exists())

    async def test_runtime_calls_observe_saved_changes_and_keyless_mode_omits_header(self):
        captured = []
        def handler(request):
            captured.append(request)
            return httpx.Response(200, json={"choices": [{"message": {"content": "有效回答"}}]})
        with self.mock_models(handler):
            await llm.llm_chat([{"role": "user", "content": "测试"}])
            service.save_settings(self.input(model="live-new-model", requiresApiKey=False))
            await llm.llm_chat([{"role": "user", "content": "测试"}])
        self.assertEqual([json.loads(row.content)["model"] for row in captured], ["environment-model", "live-new-model"])
        self.assertNotIn("authorization", captured[1].headers)

    async def test_models_endpoint_supports_api_and_chatgpt_catalog_without_inference(self):
        self.account()
        def handler(request):
            self.assertEqual(request.method, "GET")
            self.assertEqual(request.url.path, "/v1/models")
            return httpx.Response(200, json={"data": [{"id": "api-model"}], "models": [
                {"slug": "account-model", "display_name": "可用模型", "visibility": "list"},
                {"slug": "hidden", "visibility": "hide"}]})
        with self.mock_models(handler):
            api_response = await self.client.post("/api/settings/model/models", json={"model": "", "provider": "custom", "baseUrl": "https://example.invalid/v1"})
            account_response = await self.client.post("/api/settings/model/models", json={"authMode": "chatgpt", "model": ""})
        self.assertEqual(api_response.json()["models"], [{"id": "api-model", "name": "api-model"}])
        self.assertEqual(account_response.json()["models"], [{"id": "account-model", "name": "可用模型"}])

    async def test_responses_stream_requires_completion_and_uses_supported_plan_payload(self):
        self.account()
        connection = service.draft_connection(self.input(authMode="chatgpt", model="account-model"))
        events = [{"type": "response.output_text.delta", "delta": "有效回答"},
                  {"type": "response.completed", "response": {"status": "completed", "output": []}}]
        def handler(request):
            data = json.loads(request.content)
            self.assertFalse(data["store"])
            self.assertTrue(data["stream"])
            self.assertNotIn("temperature", data)
            self.assertEqual(data["input"][0]["role"], "developer")
            return httpx.Response(200, text="".join(f"data: {json.dumps(event)}\n\n" for event in events))
        with self.mock_models(handler):
            self.assertEqual(await llm.llm_chat([{"role": "system", "content": "规则"}, {"role": "user", "content": "测试"}], connection=connection), "有效回答")
            events.pop()
            with self.assertRaises(HTTPException) as caught:
                await llm.llm_chat([{"role": "system", "content": "规则"}], connection=connection)
            self.assertEqual(caught.exception.status_code, 502)

    async def test_upstream_debug_is_never_echoed_on_connection_test(self):
        with self.mock_models(lambda _: httpx.Response(401, text="environment-test-key private-oauth-token")):
            response = await self.client.post("/api/settings/model/test", json={"provider": "custom", "baseUrl": "https://example.invalid/v1", "model": "test-model"})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("environment-test-key", response.text)
        self.assertNotIn("private-oauth-token", response.text)


class ChatGPTLoginTests(SettingsFixture, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.jwk = {**jwt.algorithms.RSAAlgorithm.to_jwk(cls.signing_key.public_key(), as_dict=True), "kid": "test-signing-key"}

    def tearDown(self):
        for attempt in list(chatgpt._attempts.values()):
            chatgpt.cancel_login(attempt.id)

    def start(self, account_id=None):
        response = chatgpt.start_login(account_id)
        self.addCleanup(chatgpt.cancel_login, response["attemptId"])
        return response, chatgpt._attempts[response["attemptId"]]

    def tokens(self, attempt, **identity_changes):
        identity = {"iss": chatgpt.ISSUER, "aud": "oaiapp_issued", "sub": "oauth-subject", "email": "sample@example.invalid",
                    "iat": int(time.time()), "exp": int(time.time()) + 3600, "nonce": attempt.nonce, **identity_changes}
        return {"access_token": "synthetic-oauth-access", "refresh_token": "synthetic-oauth-refresh", "token_type": "Bearer",
                "expires_in": 3600, "scope": chatgpt.SCOPES,
                "id_token": jwt.encode(identity, self.signing_key, algorithm="RS256", headers={"kid": "test-signing-key"})}

    def transport(self, payload, captured=None):
        def handler(request):
            if captured is not None:
                captured.append(request)
            if request.method == "GET" and str(request.url) == chatgpt.JWKS_URL:
                return httpx.Response(200, json={"keys": [self.jwk]})
            return httpx.Response(200, json=payload)
        return patch.object(chatgpt.httpx, "Client", side_effect=lambda **kwargs: ORIGINAL_CLIENT(
            transport=httpx.MockTransport(handler), trust_env=False, **kwargs))

    def callback(self, attempt, **changes):
        return {"state": [attempt.state], "code": ["synthetic-code"], "client_id": ["oaiapp_issued"], **changes}

    def test_authorization_uses_fresh_pkce_state_nonce_and_persistent_host(self):
        first, attempt = self.start()
        query = parse_qs(urlsplit(first["authorizationUrl"]).query)
        expected = base64.urlsafe_b64encode(hashlib.sha256(attempt.verifier.encode()).digest()).decode().rstrip("=")
        self.assertEqual(query["code_challenge"], [expected])
        self.assertEqual(query["client_id"], ["dynamic_agent_client"])
        self.assertEqual(query["agent_name_hint"], ["Personal App"])
        self.assertEqual(query["redirect_uri"], [attempt.redirect_uri])
        second, other = self.start()
        self.assertEqual(attempt.host_id, other.host_id)
        self.assertNotEqual(attempt.state, other.state)
        self.assertNotEqual(attempt.nonce, other.nonce)
        self.assertEqual(chatgpt.login_status(first["attemptId"])["status"], "cancelled")

    def test_state_denial_and_missing_issued_client_id_do_not_exchange_code(self):
        _, attempt = self.start()
        with patch.object(chatgpt.httpx, "Client") as client:
            self.assertEqual(chatgpt.finish_login(attempt, self.callback(attempt, state=["wrong"]))[0], 400)
            self.assertEqual(chatgpt.finish_login(attempt, self.callback(attempt, client_id=["dynamic_agent_client"]))[0], 400)
            self.assertEqual(chatgpt.finish_login(attempt, self.callback(attempt, error=["access_denied"]))[0], 400)
            client.assert_not_called()
        self.assertEqual(chatgpt.public_accounts()["accounts"], [])

    def test_valid_signed_callback_saves_issued_client_and_one_time_completion(self):
        _, attempt = self.start()
        captured = []
        with self.transport(self.tokens(attempt), captured):
            status, _ = chatgpt.finish_login(attempt, self.callback(attempt))
        self.assertEqual(status, 200)
        form = parse_qs(captured[0].content.decode())
        self.assertEqual(form["client_id"], ["oaiapp_issued"])
        self.assertEqual(form["redirect_uri"], [attempt.redirect_uri])
        self.assertEqual(form["code_verifier"], [attempt.verifier])
        self.assertEqual(form["resource"], [chatgpt.RESOURCE])
        self.assertEqual(chatgpt.require_account()["subject"], "oauth-subject")
        public = json.dumps(chatgpt.public_accounts())
        self.assertNotIn("synthetic-oauth", public)
        self.assertNotIn("oaiapp_issued", public)
        self.assertEqual(chatgpt.finish_login(attempt, self.callback(attempt))[0], 400)
        account_id = chatgpt.public_accounts()["activeAccountId"]
        returning, _ = self.start(account_id)
        query = parse_qs(urlsplit(returning["authorizationUrl"]).query)
        self.assertEqual(query["client_id"], ["oaiapp_issued"])
        self.assertNotIn("agent_name_hint", query)
        self.assertNotIn("id_token_hint", query)

    def test_invalid_signature_audience_issuer_expiration_nonce_preserve_existing_account(self):
        self.account()
        for changes in ({"nonce": "wrong"}, {"aud": "wrong"}, {"iss": "https://wrong.invalid"}, {"exp": int(time.time()) - 60}):
            _, attempt = self.start()
            with self.transport(self.tokens(attempt, **changes)):
                self.assertEqual(chatgpt.finish_login(attempt, self.callback(attempt))[0], 400)
            self.assertEqual(chatgpt.public_accounts()["activeAccountId"], "account-one")
        _, attempt = self.start()
        payload = self.tokens(attempt)
        wrong_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        payload["id_token"] = jwt.encode({"sub": "wrong"}, wrong_key, algorithm="RS256", headers={"kid": "test-signing-key"})
        with self.transport(payload):
            self.assertEqual(chatgpt.finish_login(attempt, self.callback(attempt))[0], 400)

    def test_callback_scope_cannot_grant_plan_permission(self):
        _, attempt = self.start()
        payload = self.tokens(attempt)
        payload["scope"] = "openid email"
        with self.transport(payload):
            status, _ = chatgpt.finish_login(attempt, self.callback(attempt, scope=[chatgpt.SCOPES]))
        self.assertEqual(status, 200)
        with self.assertRaises(HTTPException) as caught:
            chatgpt.require_account()
        self.assertEqual(caught.exception.status_code, 403)

    def test_returning_account_cannot_change_registered_client_or_verified_identity(self):
        self.account()
        _, attempt = self.start("account-one")
        with patch.object(chatgpt.httpx, "Client") as client:
            self.assertEqual(chatgpt.finish_login(attempt, self.callback(attempt))[0], 400)
            client.assert_not_called()
        payload = self.tokens(attempt, aud="oaiapp_test_client", sub="another-subject")
        with self.transport(payload):
            self.assertEqual(chatgpt.finish_login(attempt, self.callback(attempt, client_id=["oaiapp_test_client"]))[0], 400)
        self.assertEqual(chatgpt.require_account()["access_token"], "synthetic-access")

    def test_refresh_is_serialized_and_rotates_both_tokens(self):
        self.account(expires_at=time.time() - 1)
        captured = []
        payload = {"access_token": "renewed-access", "refresh_token": "renewed-refresh", "token_type": "Bearer", "expires_in": 3600}
        with self.transport(payload, captured), ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: chatgpt.access_token(), range(2)))
        self.assertEqual(results, ["renewed-access", "renewed-access"])
        self.assertEqual(len(captured), 1)
        self.assertEqual(chatgpt.require_account()["refresh_token"], "renewed-refresh")
        form = parse_qs(captured[0].content.decode())
        self.assertEqual(form["client_id"], ["oaiapp_test_client"])
        self.assertEqual(form["refresh_token"], ["synthetic-refresh"])
        self.assertNotIn("scope", form)

    def test_revoked_refresh_requires_reauthorization_without_echoing_debug(self):
        self.account(expires_at=time.time() - 1)
        with patch.object(chatgpt.httpx, "Client", side_effect=lambda **kwargs: ORIGINAL_CLIENT(
            transport=httpx.MockTransport(lambda _: httpx.Response(400, text="private-refresh-secret")), trust_env=False, **kwargs)):
            with self.assertRaises(HTTPException) as caught:
                chatgpt.access_token()
        self.assertEqual(caught.exception.status_code, 401)
        self.assertNotIn("private-refresh-secret", caught.exception.detail)
        self.assertFalse(chatgpt.public_accounts()["accounts"][0]["connected"])

    def test_cancelled_and_expired_attempts_do_not_replace_credentials(self):
        self.account()
        response, attempt = self.start()
        chatgpt.cancel_login(response["attemptId"])
        with patch.object(chatgpt.httpx, "Client") as client:
            self.assertEqual(chatgpt.finish_login(attempt, self.callback(attempt))[0], 400)
            client.assert_not_called()
        response, attempt = self.start()
        attempt.expires_at = time.time() - 1
        self.assertEqual(chatgpt.login_status(response["attemptId"])["status"], "expired")
        self.assertEqual(chatgpt.finish_login(attempt, self.callback(attempt))[0], 400)
        self.assertEqual(chatgpt.require_account()["access_token"], "synthetic-access")

    def test_cancel_during_code_exchange_rejects_late_valid_credentials(self):
        self.account()
        response, attempt = self.start()
        entered, release = Event(), Event()
        payload = self.tokens(attempt)

        def handler(request):
            if request.method == "GET":
                return httpx.Response(200, json={"keys": [self.jwk]})
            entered.set()
            if not release.wait(3):
                raise RuntimeError("测试等待超时")
            return httpx.Response(200, json=payload)

        with patch.object(chatgpt.httpx, "Client", side_effect=lambda **kwargs: ORIGINAL_CLIENT(
            transport=httpx.MockTransport(handler), trust_env=False, **kwargs)), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(chatgpt.finish_login, attempt, self.callback(attempt))
            try:
                self.assertTrue(entered.wait(3))
                chatgpt.cancel_login(response["attemptId"])
            finally:
                release.set()
            self.assertEqual(future.result(timeout=3)[0], 400)
        self.assertEqual(chatgpt.require_account()["access_token"], "synthetic-access")
        self.assertEqual(chatgpt.public_accounts()["activeAccountId"], "account-one")

    def test_disconnect_keeps_registration_and_clears_all_tokens_when_revocation_fails(self):
        self.account()
        with patch.object(chatgpt.httpx, "Client", side_effect=httpx.ConnectError("synthetic-network-failure")):
            result = chatgpt.disconnect("account-one")
        self.assertFalse(result["revocationConfirmed"])
        row = private_store.read_document(chatgpt.ACCOUNTS_FILE)["accounts"][0]
        self.assertEqual(row["client_id"], "oaiapp_test_client")
        for name in ("access_token", "refresh_token", "id_token"):
            self.assertNotIn(name, row)
        self.assertEqual(private_store.read_document(chatgpt.ACCOUNTS_FILE)["host_id"], "urn:uuid:test-host")
