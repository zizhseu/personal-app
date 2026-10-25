"""模型调用异常回归测试，不访问外部模型或使用真实密钥。"""
import asyncio
import unittest
from unittest.mock import patch

from fastapi import HTTPException
import httpx

from app.modules.aitools import service
from app.modules.settings.models import ModelConnection


class AiCallTests(unittest.IsolatedAsyncioTestCase):
    async def call_model(self, handler):
        original_client = httpx.AsyncClient
        transport = httpx.MockTransport(handler)

        def client(**kwargs):
            # 使用内存传输，不加载系统代理或证书，也不会发出网络请求。
            return original_client(transport=transport, verify=False, trust_env=False, **kwargs)

        with patch.object(service, "current_connection", return_value=ModelConnection(
            "api_key", "custom", "https://test.invalid/v1", "test-model", api_key="local-test-key"
        )), patch.object(
            service.httpx, "AsyncClient", side_effect=client
        ):
            return await service.llm_chat([{"role": "user", "content": "测试"}])

    async def test_success_returns_message_content(self):
        result = await self.call_model(lambda _: httpx.Response(200, json={"choices": [{"message": {"content": "有效回答"}}]}))
        self.assertEqual(result, "有效回答")

    async def test_timeout_returns_actionable_504(self):
        def timeout(request):
            raise httpx.ReadTimeout("mock timeout", request=request)

        with self.assertRaises(HTTPException) as caught:
            await self.call_model(timeout)
        self.assertEqual(caught.exception.status_code, 504)

    async def test_total_duration_is_bounded_even_when_transport_keeps_waiting(self):
        async def slow_reply(_):
            await asyncio.sleep(1)
            return httpx.Response(200, json={"choices": [{"message": {"content": "过迟的回复"}}]})

        with patch.object(service, "LLM_TIMEOUT_SECONDS", 0.02), self.assertRaises(HTTPException) as caught:
            await self.call_model(slow_reply)
        self.assertEqual(caught.exception.status_code, 504)

    async def test_connection_failure_returns_502(self):
        def failure(request):
            raise httpx.ConnectError("mock failure", request=request)

        with self.assertRaises(HTTPException) as caught:
            await self.call_model(failure)
        self.assertEqual(caught.exception.status_code, 502)

    async def test_malformed_success_responses_return_502(self):
        for payload in ([], {}, {"choices": []}, {"choices": [{"message": {"content": None}}]}):
            with self.subTest(payload=payload), self.assertRaises(HTTPException) as caught:
                await self.call_model(lambda _, body=payload: httpx.Response(200, json=body))
            self.assertEqual(caught.exception.status_code, 502)

    async def test_provider_error_does_not_echo_response_secrets(self):
        with self.assertRaises(HTTPException) as caught:
            await self.call_model(lambda _: httpx.Response(401, text="private-provider-debug-value"))
        self.assertEqual(caught.exception.status_code, 502)
        self.assertNotIn("private-provider-debug-value", caught.exception.detail)
