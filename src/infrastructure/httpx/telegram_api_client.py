import logging

import httpx


class TelegramApiClient:
    def __init__(
        self,
        token: str,
        base_url: str,
        logger: logging.Logger,
        timeout_seconds: float = 20.0,
    ) -> None:
        self._token = token.strip()
        self._base_url = base_url.rstrip("/")
        self._logger = logger
        self._timeout_seconds = timeout_seconds

    async def send_message(self, chat_id: int, text: str) -> None:
        if not self._token:
            self._logger.error("TELEGRAM_TOKEN no configurado. No se puede enviar mensaje.")
            return

        url = f"{self._base_url}/bot{self._token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                self._logger.info("Respuesta Telegram sendMessage status=%s", response.status_code)
                if not data.get("ok"):
                    self._logger.error("Telegram API devolvio error: %s", data)
                else:
                    self._logger.info(
                        "Mensaje enviado correctamente. message_id=%s",
                        data.get("result", {}).get("message_id"),
                    )
        except httpx.HTTPError:
            self._logger.exception("Error llamando a Telegram sendMessage")
