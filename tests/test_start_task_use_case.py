from datetime import datetime, timezone
import logging

import pytest

from src.entities.task import StartedTask, TaskExecutionRequest
from src.use_cases.errors import LastChatNotAvailableError
from src.use_cases.start_task import StartTaskUseCase


class DummyChatStateGateway:
    def __init__(self, last_chat_id: int | None = None) -> None:
        self.last_chat_id = last_chat_id
        self.set_calls: list[int] = []

    def get_last_chat_id(self) -> int | None:
        return self.last_chat_id

    def set_last_chat_id(self, chat_id: int) -> None:
        self.last_chat_id = chat_id
        self.set_calls.append(chat_id)


class DummyTelegramNotificationGateway:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.messages.append((chat_id, text))


def _build_use_case(
    *,
    last_chat_id: int | None = None,
    fallback_chat_id: int | None = None,
    repository_name: str = "repo-default",
) -> tuple[StartTaskUseCase, DummyChatStateGateway, DummyTelegramNotificationGateway]:
    chat_gateway = DummyChatStateGateway(last_chat_id=last_chat_id)
    telegram_gateway = DummyTelegramNotificationGateway()
    use_case = StartTaskUseCase(
        chat_state_gateway=chat_gateway,
        telegram_notification_gateway=telegram_gateway,
        logger=logging.getLogger("test"),
        repository_name=repository_name,
        fallback_chat_id=fallback_chat_id,
    )
    return use_case, chat_gateway, telegram_gateway


def test_start_task_uses_existing_chat_and_normalizes_payload() -> None:
    use_case, chat_gateway, _ = _build_use_case(last_chat_id=101)

    result = use_case.start(
        TaskExecutionRequest(
            duration_seconds=2.0,
            force_fail=False,
            modified_files_count=-3,
            repository_name="  my-repo  ",
            execution_time_seconds=10.2,
        )
    )

    assert result.chat_id == 101
    assert result.modified_files_count == 0
    assert result.repository_name == "my-repo"
    assert chat_gateway.set_calls == []


def test_start_task_uses_fallback_chat_id_and_persists_it() -> None:
    use_case, chat_gateway, _ = _build_use_case(last_chat_id=None, fallback_chat_id=202)

    result = use_case.start(TaskExecutionRequest(duration_seconds=0.0))

    assert result.chat_id == 202
    assert chat_gateway.set_calls == [202]
    assert chat_gateway.last_chat_id == 202


def test_start_task_raises_when_chat_id_is_not_available() -> None:
    use_case, _, _ = _build_use_case(last_chat_id=None, fallback_chat_id=None)

    with pytest.raises(LastChatNotAvailableError):
        use_case.start(TaskExecutionRequest(duration_seconds=1.0))


def test_resolve_elapsed_seconds_prefers_provided_positive_value() -> None:
    assert StartTaskUseCase._resolve_elapsed_seconds(measured_seconds=1.0, provided_seconds=12.5) == 12.5
    assert StartTaskUseCase._resolve_elapsed_seconds(measured_seconds=0.0, provided_seconds=0.0) == 0.01


@pytest.mark.asyncio
async def test_run_task_and_notify_sends_success_message() -> None:
    use_case, _, telegram_gateway = _build_use_case(repository_name="repo-fallback")
    task = StartedTask(
        chat_id=303,
        duration_seconds=0.0,
        force_fail=False,
        modified_files_count=3,
        repository_name=None,
        execution_time_seconds=42.5,
        start_datetime=datetime(2026, 2, 17, 21, 34, 10),
        end_datetime=datetime(2026, 2, 17, 21, 35, 2, tzinfo=timezone.utc),
    )

    await use_case.run_task_and_notify(task)

    assert len(telegram_gateway.messages) == 1
    chat_id, text = telegram_gateway.messages[0]
    assert chat_id == 303
    assert "Termin" in text
    assert "Repositorio: repo-fallback" in text
    assert "Tiempo de ejecucion: 42.50s" in text
    assert "Inicio: 2026-02-17T21:34:10Z" in text
    assert "Fin: 2026-02-17T21:35:02Z" in text
    assert "Archivos modificados: 3" in text


@pytest.mark.asyncio
async def test_run_task_and_notify_sends_failure_message_when_forced() -> None:
    use_case, _, telegram_gateway = _build_use_case(repository_name="repo-fallback")
    task = StartedTask(
        chat_id=404,
        duration_seconds=0.0,
        force_fail=True,
        modified_files_count=-7,
    )

    await use_case.run_task_and_notify(task)

    assert len(telegram_gateway.messages) == 1
    chat_id, text = telegram_gateway.messages[0]
    assert chat_id == 404
    assert "Fall" in text
    assert "Repositorio: repo-fallback" in text
    assert "Archivos modificados: 0" in text
