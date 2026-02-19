import logging

import pytest

from src.use_cases.errors import InvalidTelegramSecretError
from src.use_cases.get_last_chat import GetLastChatUseCase
from src.use_cases.process_telegram_webhook import ProcessTelegramWebhookUseCase


class DummyChatStateGateway:
    def __init__(self, last_chat_id: int | None = None) -> None:
        self.last_chat_id = last_chat_id
        self.set_calls: list[int] = []

    def get_last_chat_id(self) -> int | None:
        return self.last_chat_id

    def set_last_chat_id(self, chat_id: int) -> None:
        self.last_chat_id = chat_id
        self.set_calls.append(chat_id)


def test_get_last_chat_use_case_returns_gateway_value() -> None:
    gateway = DummyChatStateGateway(last_chat_id=777)
    use_case = GetLastChatUseCase(chat_state_gateway=gateway, logger=logging.getLogger("test"))

    assert use_case.execute() == 777


def test_process_telegram_webhook_rejects_invalid_secret() -> None:
    gateway = DummyChatStateGateway()
    use_case = ProcessTelegramWebhookUseCase(
        chat_state_gateway=gateway,
        expected_secret="expected-secret",
        logger=logging.getLogger("test"),
    )

    with pytest.raises(InvalidTelegramSecretError):
        use_case.execute(update={"update_id": 1}, provided_secret="wrong-secret")

    assert gateway.set_calls == []


def test_process_telegram_webhook_updates_last_chat_id() -> None:
    gateway = DummyChatStateGateway()
    use_case = ProcessTelegramWebhookUseCase(
        chat_state_gateway=gateway,
        expected_secret="",
        logger=logging.getLogger("test"),
    )

    chat_id = use_case.execute(
        update={"update_id": 10, "message": {"chat": {"id": 999}}},
        provided_secret=None,
    )

    assert chat_id == 999
    assert gateway.set_calls == [999]
    assert gateway.last_chat_id == 999


def test_process_telegram_webhook_accepts_update_without_chat_id() -> None:
    gateway = DummyChatStateGateway()
    use_case = ProcessTelegramWebhookUseCase(
        chat_state_gateway=gateway,
        expected_secret="",
        logger=logging.getLogger("test"),
    )

    chat_id = use_case.execute(update={"update_id": 11, "inline_query": {"id": "x"}}, provided_secret=None)

    assert chat_id is None
    assert gateway.set_calls == []
