from typing import Any
import logging

import httpx
import pytest

import src.infrastructure.httpx.telegram_api_client as telegram_api_module
import src.infrastructure.httpx.telegram_webhook_client as webhook_module
from src.infrastructure.httpx.telegram_api_client import TelegramApiClient
from src.infrastructure.httpx.telegram_webhook_client import TelegramWebhookClient


class DummyAsyncResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200, raise_http_error: bool = False) -> None:
        self._payload = payload
        self.status_code = status_code
        self._raise_http_error = raise_http_error

    def raise_for_status(self) -> None:
        if self._raise_http_error:
            raise httpx.HTTPError("boom")

    def json(self) -> dict[str, Any]:
        return self._payload


class DummyAsyncClient:
    def __init__(self, timeout: float, response: DummyAsyncResponse, captured: dict[str, Any]) -> None:
        captured["timeout"] = timeout
        self._response = response
        self._captured = captured

    async def __aenter__(self) -> "DummyAsyncClient":
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False

    async def post(self, url: str, json: dict[str, Any]) -> DummyAsyncResponse:
        self._captured["url"] = url
        self._captured["json"] = json
        return self._response


class DummyResponse:
    def __init__(self, payload: dict[str, Any], raise_http_error: bool = False) -> None:
        self._payload = payload
        self._raise_http_error = raise_http_error

    def raise_for_status(self) -> None:
        if self._raise_http_error:
            raise httpx.HTTPError("boom")

    def json(self) -> dict[str, Any]:
        return self._payload


class DummyClient:
    def __init__(
        self,
        timeout: float,
        captured: dict[str, Any],
        post_response: DummyResponse | None = None,
        get_response: DummyResponse | None = None,
    ) -> None:
        self._captured = captured
        self._captured["timeout"] = timeout
        self._post_response = post_response or DummyResponse({"ok": True})
        self._get_response = get_response or DummyResponse({"ok": True, "result": {}})

    def __enter__(self) -> "DummyClient":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False

    def post(self, endpoint: str, data: dict[str, Any]) -> DummyResponse:
        self._captured["post_endpoint"] = endpoint
        self._captured["post_data"] = data
        return self._post_response

    def get(self, endpoint: str) -> DummyResponse:
        self._captured["get_endpoint"] = endpoint
        return self._get_response


@pytest.mark.asyncio
async def test_telegram_api_client_skips_request_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    def _failing_async_client(*args: object, **kwargs: object) -> object:
        raise AssertionError("AsyncClient should not be created when TELEGRAM_TOKEN is empty")

    monkeypatch.setattr(telegram_api_module.httpx, "AsyncClient", _failing_async_client)
    client = TelegramApiClient(
        token="",
        base_url="https://api.telegram.org",
        logger=logging.getLogger("test"),
    )

    await client.send_message(chat_id=123, text="hello")


@pytest.mark.asyncio
async def test_telegram_api_client_posts_message(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    response = DummyAsyncResponse(payload={"ok": True, "result": {"message_id": 1}}, status_code=200)

    def _factory(*, timeout: float) -> DummyAsyncClient:
        return DummyAsyncClient(timeout=timeout, response=response, captured=captured)

    monkeypatch.setattr(telegram_api_module.httpx, "AsyncClient", _factory)

    client = TelegramApiClient(
        token="bot-token",
        base_url="https://api.telegram.org/",
        logger=logging.getLogger("test"),
    )
    await client.send_message(chat_id=321, text="message")

    assert captured["timeout"] == 20.0
    assert captured["url"] == "https://api.telegram.org/botbot-token/sendMessage"
    assert captured["json"] == {"chat_id": 321, "text": "message"}


@pytest.mark.asyncio
async def test_telegram_api_client_handles_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}
    response = DummyAsyncResponse(payload={"ok": False}, raise_http_error=True)

    def _factory(*, timeout: float) -> DummyAsyncClient:
        return DummyAsyncClient(timeout=timeout, response=response, captured=captured)

    monkeypatch.setattr(telegram_api_module.httpx, "AsyncClient", _factory)
    client = TelegramApiClient(
        token="bot-token",
        base_url="https://api.telegram.org",
        logger=logging.getLogger("test"),
    )

    await client.send_message(chat_id=10, text="x")
    assert captured["json"]["chat_id"] == 10


def test_telegram_webhook_client_set_webhook_with_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _factory(*, timeout: float) -> DummyClient:
        return DummyClient(timeout=timeout, captured=captured, post_response=DummyResponse({"ok": True}))

    monkeypatch.setattr(webhook_module.httpx, "Client", _factory)
    client = TelegramWebhookClient(telegram_token="abc", telegram_api_base_url="https://api.telegram.org/")

    result = client.set_webhook(
        webhook_url="https://api.example.com/telegram/webhook",
        secret_token="secret-value",
        drop_pending_updates=True,
    )

    assert result == {"ok": True}
    assert captured["post_endpoint"] == "https://api.telegram.org/botabc/setWebhook"
    assert captured["post_data"]["url"] == "https://api.example.com/telegram/webhook"
    assert captured["post_data"]["secret_token"] == "secret-value"
    assert captured["post_data"]["drop_pending_updates"] == "true"


def test_telegram_webhook_client_get_webhook_info(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def _factory(*, timeout: float) -> DummyClient:
        return DummyClient(
            timeout=timeout,
            captured=captured,
            get_response=DummyResponse({"ok": True, "result": {"pending_update_count": 0}}),
        )

    monkeypatch.setattr(webhook_module.httpx, "Client", _factory)
    client = TelegramWebhookClient(telegram_token="abc", telegram_api_base_url="https://api.telegram.org")

    result = client.get_webhook_info()

    assert result["ok"] is True
    assert captured["get_endpoint"] == "https://api.telegram.org/botabc/getWebhookInfo"
