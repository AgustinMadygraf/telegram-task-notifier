from datetime import datetime

from src.entities.task import StartedTask, TaskExecutionRequest
from src.interface_adapters.controllers.tasks_controller import TasksController
from src.interface_adapters.controllers.telegram_controller import TelegramController
from src.interface_adapters.presenters.task_presenter import present_task_started
from src.interface_adapters.presenters.telegram_presenter import present_last_chat, present_webhook_result


class DummyStartTaskUseCase:
    def __init__(self, task: StartedTask) -> None:
        self.task = task
        self.received_request: TaskExecutionRequest | None = None

    def start(self, request: TaskExecutionRequest) -> StartedTask:
        self.received_request = request
        return self.task


class DummyProcessWebhookUseCase:
    def __init__(self, result: int | None) -> None:
        self.result = result
        self.calls: list[tuple[dict[str, object], str | None]] = []

    def execute(self, update: dict[str, object], provided_secret: str | None) -> int | None:
        self.calls.append((update, provided_secret))
        return self.result


class DummyGetLastChatUseCase:
    def __init__(self, result: int | None) -> None:
        self.result = result

    def execute(self) -> int | None:
        return self.result


def test_tasks_controller_schedules_background_task_and_presents_response() -> None:
    started_task = StartedTask(chat_id=1, duration_seconds=2.0, force_fail=False)
    start_task_use_case = DummyStartTaskUseCase(task=started_task)
    controller = TasksController(start_task_use_case=start_task_use_case)  # type: ignore[arg-type]
    scheduled: list[StartedTask] = []

    response = controller.handle_start_task(
        request=TaskExecutionRequest(duration_seconds=2.0),
        schedule_background_task=lambda task: scheduled.append(task),
    )

    assert response["status"] == "started"
    assert response["chat_id"] == 1
    assert scheduled == [started_task]
    assert start_task_use_case.received_request is not None


def test_telegram_controller_delegates_to_use_cases() -> None:
    process_use_case = DummyProcessWebhookUseCase(result=333)
    last_chat_use_case = DummyGetLastChatUseCase(result=444)
    controller = TelegramController(  # type: ignore[arg-type]
        process_webhook_use_case=process_use_case,
        get_last_chat_use_case=last_chat_use_case,
    )

    webhook_response = controller.handle_webhook({"update_id": 1}, "secret")
    last_chat_response = controller.handle_last_chat()

    assert webhook_response == {"ok": True, "captured_chat_id": 333}
    assert last_chat_response == {"last_chat_id": 444}
    assert process_use_case.calls == [({"update_id": 1}, "secret")]


def test_presenters_return_expected_payloads() -> None:
    task_response = present_task_started(
        StartedTask(
            chat_id=7,
            duration_seconds=0.5,
            force_fail=False,
            start_datetime=datetime(2026, 2, 18, 10, 0, 0),
            end_datetime=datetime(2026, 2, 18, 10, 0, 1),
        )
    )

    assert task_response["start_datetime"] == "2026-02-18T10:00:00Z"
    assert task_response["end_datetime"] == "2026-02-18T10:00:01Z"
    assert present_webhook_result(11) == {"ok": True, "captured_chat_id": 11}
    assert present_last_chat(22) == {"last_chat_id": 22}
