import logging
from typing import Any

from src.entities.telegram import extract_chat_id
from src.shared.log_safety import mask_identifier
from src.use_cases.errors import InvalidTelegramSecretError
from src.use_cases.ports import ChatStateGateway


class ProcessTelegramWebhookUseCase:
    def __init__(
        self,
        chat_state_gateway: ChatStateGateway,
        expected_secret: str,
        logger: logging.Logger,
        debug_enabled: bool = False,
        mask_sensitive_ids: bool = True,
    ) -> None:
        self._chat_state_gateway = chat_state_gateway
        self._expected_secret = expected_secret.strip()
        self._logger = logger
        self._debug_enabled = debug_enabled
        self._mask_sensitive_ids = mask_sensitive_ids

    def _safe_chat_id(self, chat_id: int | None) -> str:
        if chat_id is None:
            return ""
        if not self._mask_sensitive_ids:
            return str(chat_id)
        return mask_identifier(chat_id, prefix=2, suffix=2)

    def execute(self, update: dict[str, Any], provided_secret: str | None, request_id: str = "") -> int | None:
        update_id = update.get("update_id")
        self._logger.info(
            "telegram_webhook_received",
            extra={
                "event": "telegram_webhook_received",
                "request_id": request_id,
                "update_id": update_id,
                "has_secret_header": bool(provided_secret),
            },
        )

        if self._expected_secret and provided_secret != self._expected_secret:
            self._logger.warning(
                "telegram_webhook_rejected",
                extra={
                    "event": "telegram_webhook_rejected",
                    "request_id": request_id,
                    "update_id": update_id,
                    "reason": "invalid_secret",
                    "has_secret_header": bool(provided_secret),
                },
            )
            raise InvalidTelegramSecretError("Invalid Telegram secret token")

        if self._debug_enabled:
            self._logger.debug(
                "telegram_webhook_debug",
                extra={
                    "event": "telegram_webhook_debug",
                    "request_id": request_id,
                    "update_id": update_id,
                    "top_level_keys": sorted(update.keys()),
                },
            )

        chat_id = extract_chat_id(update)
        if chat_id is not None:
            self._chat_state_gateway.set_last_chat_id(chat_id)
            self._logger.info(
                "telegram_webhook_chat_captured",
                extra={
                    "event": "telegram_webhook_chat_captured",
                    "request_id": request_id,
                    "update_id": update_id,
                    "chat_id": self._safe_chat_id(chat_id),
                },
            )
        else:
            self._logger.info(
                "telegram_webhook_no_chat_id",
                extra={
                    "event": "telegram_webhook_no_chat_id",
                    "request_id": request_id,
                    "update_id": update_id,
                    "top_level_keys": sorted(update.keys()),
                },
            )

        return chat_id
