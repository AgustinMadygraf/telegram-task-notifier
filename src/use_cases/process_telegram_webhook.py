import logging
from typing import Any

from src.entities.telegram import extract_chat_id
from src.use_cases.errors import InvalidTelegramSecretError
from src.use_cases.ports import ChatStateGateway


class ProcessTelegramWebhookUseCase:
    def __init__(
        self,
        chat_state_gateway: ChatStateGateway,
        expected_secret: str,
        logger: logging.Logger,
    ) -> None:
        self._chat_state_gateway = chat_state_gateway
        self._expected_secret = expected_secret.strip()
        self._logger = logger

    def execute(self, update: dict[str, Any], provided_secret: str | None) -> int | None:
        self._logger.info(
            "Webhook recibido. update_id=%s has_secret_header=%s",
            update.get("update_id"),
            bool(provided_secret),
        )

        if self._expected_secret and provided_secret != self._expected_secret:
            self._logger.warning("Webhook rechazado por secret invalido.")
            raise InvalidTelegramSecretError("Invalid Telegram secret token")

        chat_id = extract_chat_id(update)
        if chat_id is not None:
            self._chat_state_gateway.set_last_chat_id(chat_id)
            self._logger.info("last_chat_id actualizado: %s", chat_id)
        else:
            self._logger.info("Webhook sin chat_id extraible. keys=%s", list(update.keys()))

        return chat_id

