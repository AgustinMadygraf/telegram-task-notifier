from typing import Any

import httpx


class TelegramWebhookClient:
    def __init__(self, telegram_token: str, telegram_api_base_url: str, timeout_seconds: float = 20.0) -> None:
        self._telegram_token = telegram_token.strip()
        self._telegram_api_base_url = telegram_api_base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def set_webhook(
        self,
        webhook_url: str,
        secret_token: str | None,
        drop_pending_updates: bool,
    ) -> dict[str, Any]:
        endpoint = f"{self._telegram_api_base_url}/bot{self._telegram_token}/setWebhook"
        payload: dict[str, Any] = {
            "url": webhook_url,
            "drop_pending_updates": str(drop_pending_updates).lower(),
        }
        if secret_token:
            payload["secret_token"] = secret_token

        with httpx.Client(timeout=self._timeout_seconds) as client:
            response = client.post(endpoint, data=payload)
            response.raise_for_status()
            return response.json()

    def get_webhook_info(self) -> dict[str, Any]:
        endpoint = f"{self._telegram_api_base_url}/bot{self._telegram_token}/getWebhookInfo"
        with httpx.Client(timeout=self._timeout_seconds) as client:
            response = client.get(endpoint)
            response.raise_for_status()
            return response.json()
