import logging

from src.infrastructure.httpx.telegram_api_client import TelegramApiClient
from src.use_cases.ports import TelegramNotificationGateway


class HttpxTelegramNotificationGateway(TelegramNotificationGateway):
    def __init__(self, telegram_api_client: TelegramApiClient, logger: logging.Logger) -> None:
        self._telegram_api_client = telegram_api_client
        self._logger = logger

    async def send_message(self, chat_id: int, text: str) -> None:
        self._logger.info("Enviando mensaje a Telegram. chat_id=%s text=%s", chat_id, text)
        await self._telegram_api_client.send_message(chat_id=chat_id, text=text)

