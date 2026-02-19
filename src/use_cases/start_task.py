import asyncio
import logging
import time

from src.entities.task import StartedTask, TaskExecutionRequest
from src.shared.datetime_utils import to_utc_iso
from src.use_cases.errors import LastChatNotAvailableError
from src.use_cases.ports import ChatStateGateway, TelegramNotificationGateway


class StartTaskUseCase:
    _MIN_REPORTED_EXECUTION_SECONDS = 0.01

    def __init__(
        self,
        chat_state_gateway: ChatStateGateway,
        telegram_notification_gateway: TelegramNotificationGateway,
        logger: logging.Logger,
        repository_name: str,
        fallback_chat_id: int | None = None,
    ) -> None:
        self._chat_state_gateway = chat_state_gateway
        self._telegram_notification_gateway = telegram_notification_gateway
        self._logger = logger
        self._repository_name = repository_name.strip() or "unknown-repository"
        self._fallback_chat_id = fallback_chat_id

    @staticmethod
    def _normalize_modified_files_count(modified_files_count: int) -> int:
        if modified_files_count < 0:
            return 0
        return modified_files_count

    @staticmethod
    def _normalize_repository_name(repository_name: str | None) -> str:
        if repository_name is None:
            return ""
        return repository_name.strip()

    def _build_notification_message(
        self,
        status_text: str,
        task: StartedTask,
        elapsed_seconds: float,
    ) -> str:
        modified_files_count = self._normalize_modified_files_count(task.modified_files_count)
        files_line = f"Archivos modificados: {modified_files_count}"

        repository_name = self._normalize_repository_name(task.repository_name)
        if not repository_name:
            repository_name = self._repository_name

        return "\n".join(
            list(
                filter(
                    None,
                    [
                        status_text,
                        f"Repositorio: {repository_name}",
                        f"Tiempo de ejecucion: {elapsed_seconds:.2f}s",
                        (f"Inicio: {to_utc_iso(task.start_datetime)}" if task.start_datetime is not None else None),
                        (f"Fin: {to_utc_iso(task.end_datetime)}" if task.end_datetime is not None else None),
                        files_line,
                    ],
                )
            )
        )

    @classmethod
    def _resolve_elapsed_seconds(cls, measured_seconds: float, provided_seconds: float | None) -> float:
        if provided_seconds is not None and provided_seconds > 0:
            return max(provided_seconds, cls._MIN_REPORTED_EXECUTION_SECONDS)
        return max(measured_seconds, cls._MIN_REPORTED_EXECUTION_SECONDS)

    def start(self, request: TaskExecutionRequest) -> StartedTask:
        modified_files_count = self._normalize_modified_files_count(request.modified_files_count)
        repository_name = self._normalize_repository_name(request.repository_name)
        self._logger.info(
            "POST /tasks/start payload=%s",
            {
                "duration_seconds": request.duration_seconds,
                "force_fail": request.force_fail,
                "modified_files_count": modified_files_count,
                "repository_name": repository_name,
                "execution_time_seconds": request.execution_time_seconds,
                "start_datetime": to_utc_iso(request.start_datetime),
                "end_datetime": to_utc_iso(request.end_datetime),
            },
        )
        chat_id = self._chat_state_gateway.get_last_chat_id()
        if chat_id is None:
            if self._fallback_chat_id is not None:
                chat_id = self._fallback_chat_id
                self._chat_state_gateway.set_last_chat_id(chat_id)
                self._logger.info("Usando TELEGRAM_CHAT_ID fallback: %s", chat_id)
            else:
                raise LastChatNotAvailableError(
                    "last_chat_id es null. Escribile al bot primero para capturarlo "
                    "o configura TELEGRAM_CHAT_ID en .env."
                )

        self._logger.info("Programando tarea para chat_id=%s", chat_id)
        return StartedTask(
            chat_id=chat_id,
            duration_seconds=request.duration_seconds,
            force_fail=request.force_fail,
            modified_files_count=modified_files_count,
            repository_name=repository_name or None,
            execution_time_seconds=request.execution_time_seconds,
            start_datetime=request.start_datetime,
            end_datetime=request.end_datetime,
        )

    async def run_task_and_notify(self, task: StartedTask) -> None:
        self._logger.info(
            "Tarea iniciada. chat_id=%s duration_seconds=%s force_fail=%s modified_files_count=%s",
            task.chat_id,
            task.duration_seconds,
            task.force_fail,
            task.modified_files_count,
        )
        started_at = time.perf_counter()
        try:
            await asyncio.sleep(task.duration_seconds)
            self._logger.info("Tarea finalizo espera. chat_id=%s", task.chat_id)

            if task.force_fail:
                raise RuntimeError("Falla forzada para prueba MVP.")

            measured_seconds = time.perf_counter() - started_at
            elapsed_seconds = self._resolve_elapsed_seconds(measured_seconds, task.execution_time_seconds)
            message = self._build_notification_message("Termin\u00e9", task, elapsed_seconds)
            await self._telegram_notification_gateway.send_message(task.chat_id, message)
        except Exception:
            self._logger.exception("La tarea fallo.")
            measured_seconds = time.perf_counter() - started_at
            elapsed_seconds = self._resolve_elapsed_seconds(measured_seconds, task.execution_time_seconds)
            message = self._build_notification_message("Fall\u00f3", task, elapsed_seconds)
            await self._telegram_notification_gateway.send_message(task.chat_id, message)
