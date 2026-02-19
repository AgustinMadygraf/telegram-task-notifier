from typing import Any

from src.interface_adapters.presenters.telegram_presenter import (
    present_last_chat,
    present_webhook_result,
)
from src.use_cases.get_last_chat import GetLastChatUseCase
from src.use_cases.process_telegram_webhook import ProcessTelegramWebhookUseCase


class TelegramController:
    def __init__(
        self,
        process_webhook_use_case: ProcessTelegramWebhookUseCase,
        get_last_chat_use_case: GetLastChatUseCase,
    ) -> None:
        self._process_webhook_use_case = process_webhook_use_case
        self._get_last_chat_use_case = get_last_chat_use_case

    def handle_webhook(
        self, update: dict[str, Any], provided_secret: str | None, request_id: str = ""
    ) -> dict[str, Any]:
        captured_chat_id = self._process_webhook_use_case.execute(
            update=update,
            provided_secret=provided_secret,
            request_id=request_id,
        )
        return present_webhook_result(captured_chat_id)

    def handle_last_chat(self) -> dict[str, Any]:
        return present_last_chat(self._get_last_chat_use_case.execute())
