from collections.abc import Callable

from src.entities.task import StartedTask, TaskExecutionRequest
from src.interface_adapters.presenters.task_presenter import present_task_started
from src.use_cases.start_task import StartTaskUseCase


class TasksController:
    def __init__(self, start_task_use_case: StartTaskUseCase) -> None:
        self._start_task_use_case = start_task_use_case

    def handle_start_task(
        self,
        request: TaskExecutionRequest,
        schedule_background_task: Callable[[StartedTask], None],
    ) -> dict[str, object]:
        task = self._start_task_use_case.start(request)
        schedule_background_task(task)
        return present_task_started(task)
