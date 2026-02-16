import os
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.entities.task import TaskExecutionRequest
from src.infrastructure.fastapi.schemas import TaskStartRequestModel
from src.infrastructure.httpx.telegram_api_client import TelegramApiClient
from src.interface_adapters.controllers.tasks_controller import TasksController
from src.interface_adapters.controllers.telegram_controller import TelegramController
from src.interface_adapters.gateways.file_chat_state_gateway import FileChatStateGateway
from src.interface_adapters.gateways.telegram_notification_gateway import (
    HttpxTelegramNotificationGateway,
)
from src.shared.config import load_settings
from src.shared.logger import configure_logging, get_logger
from src.use_cases.errors import InvalidTelegramSecretError, LastChatNotAvailableError
from src.use_cases.get_last_chat import GetLastChatUseCase
from src.use_cases.process_telegram_webhook import ProcessTelegramWebhookUseCase
from src.use_cases.start_task import StartTaskUseCase

configure_logging()
logger = get_logger("telegram-task-notifier")

settings = load_settings()
if not settings.env_path.exists():
    logger.info("No se encontro .env en %s", settings.env_path)
else:
    if settings.loaded_env_keys:
        logger.info(".env cargado. Variables inyectadas: %s", ", ".join(settings.loaded_env_keys))
    else:
        logger.info(".env encontrado, pero no se inyecto ninguna variable nueva.")

raw_chat_id_env = os.getenv("TELEGRAM_CHAT_ID", "").strip()
if raw_chat_id_env and settings.telegram_chat_id is None:
    logger.warning("TELEGRAM_CHAT_ID esta definido pero no es un entero valido.")
elif settings.telegram_chat_id is not None:
    logger.info("TELEGRAM_CHAT_ID fallback activo: %s", settings.telegram_chat_id)

chat_state_gateway = FileChatStateGateway(settings.state_file_path, logger)
telegram_api_client = TelegramApiClient(
    token=settings.telegram_token,
    base_url=settings.telegram_api_base_url,
    logger=logger,
)
telegram_notification_gateway = HttpxTelegramNotificationGateway(telegram_api_client, logger)

process_webhook_use_case = ProcessTelegramWebhookUseCase(
    chat_state_gateway=chat_state_gateway,
    expected_secret=settings.telegram_webhook_secret,
    logger=logger,
)
get_last_chat_use_case = GetLastChatUseCase(chat_state_gateway=chat_state_gateway, logger=logger)
start_task_use_case = StartTaskUseCase(
    chat_state_gateway=chat_state_gateway,
    telegram_notification_gateway=telegram_notification_gateway,
    logger=logger,
    repository_name=settings.repository_name,
    fallback_chat_id=settings.telegram_chat_id,
)

telegram_controller = TelegramController(
    process_webhook_use_case=process_webhook_use_case,
    get_last_chat_use_case=get_last_chat_use_case,
)
tasks_controller = TasksController(start_task_use_case=start_task_use_case)

app = FastAPI(title="Telegram Task Notifier MVP")


@app.post("/telegram/webhook")
async def telegram_webhook(
    update: dict[str, Any],
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict[str, Any]:
    try:
        return telegram_controller.handle_webhook(update, x_telegram_bot_api_secret_token)
    except InvalidTelegramSecretError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@app.get("/telegram/last_chat")
async def telegram_last_chat() -> dict[str, Any]:
    return telegram_controller.handle_last_chat()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    raw_body = await request.body()
    raw_text = raw_body.decode("utf-8", errors="replace")
    logger.error(
        "Validation error. method=%s path=%s body=%s errors=%s",
        request.method,
        request.url.path,
        raw_text,
        exc.errors(),
    )

    detail: Any = exc.errors()
    if request.url.path == "/tasks/start":
        detail = {
            "errors": exc.errors(),
            "hint": (
                "JSON invalido. En CMD usa: "
                "curl -X POST http://127.0.0.1:8000/tasks/start "
                "-H \"Content-Type: application/json\" "
                "-d \"{\\\"duration_seconds\\\":2,\\\"force_fail\\\":false,"
                "\\\"commit_proposal\\\":\\\"feat: notificar resumen en telegram\\\","
                "\\\"repository_name\\\":\\\"telegram-task-notifier\\\","
                "\\\"execution_time_seconds\\\":42.5}\""
            ),
        }

    return JSONResponse(status_code=422, content={"detail": detail})


@app.post("/tasks/start")
async def tasks_start(
    payload: TaskStartRequestModel,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    request = TaskExecutionRequest(
        duration_seconds=payload.duration_seconds,
        force_fail=payload.force_fail,
        commit_proposal=payload.commit_proposal,
        repository_name=payload.repository_name,
        execution_time_seconds=payload.execution_time_seconds,
    )

    try:
        return tasks_controller.handle_start_task(
            request=request,
            schedule_background_task=lambda task: background_tasks.add_task(
                start_task_use_case.run_task_and_notify,
                task,
            ),
        )
    except LastChatNotAvailableError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
