import os
from uuid import uuid4
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.entities.task import TaskExecutionRequest
from src.infrastructure.fastapi.contact_router import create_contact_router
from src.infrastructure.fastapi.schemas import TaskStartRequestModel
from src.infrastructure.rate_limit.in_memory_rate_limiter_gateway import InMemoryRateLimiterGateway
from src.infrastructure.request_id.context_request_id_provider import (
    ContextRequestIdProvider,
    reset_request_id,
    set_request_id,
)
from src.infrastructure.httpx.telegram_api_client import TelegramApiClient
from src.infrastructure.smtp.smtp_mail_gateway import SmtpMailGateway
from src.interface_adapters.controllers.tasks_controller import TasksController
from src.interface_adapters.controllers.telegram_controller import TelegramController
from src.interface_adapters.gateways.file_chat_state_gateway import FileChatStateGateway
from src.interface_adapters.gateways.telegram_notification_gateway import (
    HttpxTelegramNotificationGateway,
)
from src.shared.config import Settings, load_settings, validate_startup_settings
from src.shared.logger import configure_logging, get_logger
from src.use_cases.errors import InvalidTelegramSecretError, LastChatNotAvailableError
from src.use_cases.get_last_chat import GetLastChatUseCase
from src.use_cases.process_telegram_webhook import ProcessTelegramWebhookUseCase
from src.use_cases.send_mail import SendMailUseCase
from src.use_cases.start_task import StartTaskUseCase
from src.use_cases.submit_contact import SubmitContactUseCase

configure_logging()
logger = get_logger("datamaq-communications-api")

_CONTACT_PATHS = {"/contact", "/mail"}


def _request_id_from_state(request: Request) -> str:
    value = getattr(request.state, "request_id", "")
    if isinstance(value, str) and value.strip():
        return value
    generated = str(uuid4())
    request.state.request_id = generated
    return generated


def _error_response(request: Request, status_code: int, code: str, message: str) -> JSONResponse:
    request_id = _request_id_from_state(request)
    payload = {
        "request_id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }
    return JSONResponse(status_code=status_code, content=payload, headers={"X-Request-Id": request_id})

def _log_environment_configuration(app_settings: Settings) -> None:
    if not app_settings.env_path.exists():
        logger.info("No se encontro .env en %s", app_settings.env_path)
    else:
        if app_settings.loaded_env_keys:
            logger.info(".env cargado. Variables inyectadas: %s", ", ".join(app_settings.loaded_env_keys))
        else:
            logger.info(".env encontrado, pero no se inyecto ninguna variable nueva.")

    raw_chat_id_env = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if raw_chat_id_env and app_settings.telegram_chat_id is None:
        logger.warning("TELEGRAM_CHAT_ID esta definido pero no es un entero valido.")
    elif app_settings.telegram_chat_id is not None:
        logger.info("TELEGRAM_CHAT_ID fallback activo: %s", app_settings.telegram_chat_id)


def create_app(custom_settings: Settings | None = None) -> FastAPI:
    effective_settings = custom_settings or load_settings()
    validate_startup_settings(effective_settings)
    _log_environment_configuration(effective_settings)

    chat_state_gateway = FileChatStateGateway(effective_settings.state_file_path, logger)
    telegram_api_client = TelegramApiClient(
        token=effective_settings.telegram_token,
        base_url=effective_settings.telegram_api_base_url,
        logger=logger,
    )
    telegram_notification_gateway = HttpxTelegramNotificationGateway(telegram_api_client, logger)

    process_webhook_use_case = ProcessTelegramWebhookUseCase(
        chat_state_gateway=chat_state_gateway,
        expected_secret=effective_settings.telegram_webhook_secret,
        logger=logger,
    )
    get_last_chat_use_case = GetLastChatUseCase(chat_state_gateway=chat_state_gateway, logger=logger)
    start_task_use_case = StartTaskUseCase(
        chat_state_gateway=chat_state_gateway,
        telegram_notification_gateway=telegram_notification_gateway,
        logger=logger,
        repository_name=effective_settings.repository_name,
        fallback_chat_id=effective_settings.telegram_chat_id,
    )
    mail_gateway = SmtpMailGateway(
        host=effective_settings.smtp_host,
        port=effective_settings.smtp_port,
        username=effective_settings.smtp_user,
        password=effective_settings.smtp_pass,
        use_tls=effective_settings.smtp_tls,
        sender=effective_settings.smtp_from,
        default_recipient=effective_settings.smtp_to_default,
        logger=logger,
    )
    send_mail_use_case = SendMailUseCase(mail_gateway=mail_gateway, logger=logger)
    rate_limiter_gateway = InMemoryRateLimiterGateway()
    request_id_provider = ContextRequestIdProvider()
    submit_contact_use_case = SubmitContactUseCase(
        rate_limiter_gateway=rate_limiter_gateway,
        request_id_provider=request_id_provider,
        logger=logger,
        honeypot_field=effective_settings.honeypot_field,
        rate_limit_window=effective_settings.rate_limit_window,
        rate_limit_max=effective_settings.rate_limit_max,
    )

    telegram_controller = TelegramController(
        process_webhook_use_case=process_webhook_use_case,
        get_last_chat_use_case=get_last_chat_use_case,
    )
    tasks_controller = TasksController(start_task_use_case=start_task_use_case)

    fastapi_app = FastAPI(title="Datamaq Communications API")
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=list(effective_settings.cors_allowed_origins),
        allow_credentials=False,
        allow_methods=["POST", "OPTIONS"],
        allow_headers=["*"],
    )

    fastapi_app.state.send_mail_use_case = send_mail_use_case
    fastapi_app.state.submit_contact_use_case = submit_contact_use_case
    fastapi_app.include_router(
        create_contact_router(
            submit_contact_use_case=submit_contact_use_case,
            send_mail_use_case=send_mail_use_case,
            logger=logger,
        )
    )

    @fastapi_app.middleware("http")
    async def request_id_middleware(request: Request, call_next: Any) -> JSONResponse:
        incoming_request_id = request.headers.get("X-Request-Id", "").strip()
        request_id = incoming_request_id or str(uuid4())
        request.state.request_id = request_id
        token = set_request_id(request_id)
        try:
            response = await call_next(request)
        finally:
            reset_request_id(token)

        response.headers["X-Request-Id"] = request_id
        return response

    @fastapi_app.post("/telegram/webhook")
    async def telegram_webhook(
        update: dict[str, Any],
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        try:
            return telegram_controller.handle_webhook(update, x_telegram_bot_api_secret_token)
        except InvalidTelegramSecretError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @fastapi_app.get("/telegram/last_chat")
    async def telegram_last_chat() -> dict[str, Any]:
        return telegram_controller.handle_last_chat()

    @fastapi_app.exception_handler(RequestValidationError)
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

        if request.url.path in _CONTACT_PATHS:
            return _error_response(
                request=request,
                status_code=422,
                code="VALIDATION_ERROR",
                message="Invalid request payload",
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
                    "\\\"modified_files_count\\\":2,"
                    "\\\"repository_name\\\":\\\"datamaq-communications-api\\\","
                    "\\\"execution_time_seconds\\\":42.5,"
                    "\\\"start_datetime\\\":\\\"2026-02-17T21:34:10Z\\\","
                    "\\\"end_datetime\\\":\\\"2026-02-17T21:35:02Z\\\"}\""
                ),
            }

        return JSONResponse(status_code=422, content={"detail": detail})

    @fastapi_app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        if request.url.path in _CONTACT_PATHS:
            code = "BAD_REQUEST"
            message = "Bad request"
            if isinstance(exc.detail, dict):
                code = str(exc.detail.get("code", code))
                message = str(exc.detail.get("message", message))
            elif isinstance(exc.detail, str):
                message = exc.detail
            return _error_response(request=request, status_code=exc.status_code, code=code, message=message)

        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=exc.headers)

    @fastapi_app.post("/tasks/start")
    async def tasks_start(
        payload: TaskStartRequestModel,
        background_tasks: BackgroundTasks,
    ) -> dict[str, Any]:
        request = TaskExecutionRequest(
            duration_seconds=payload.duration_seconds,
            force_fail=payload.force_fail,
            modified_files_count=payload.modified_files_count,
            repository_name=payload.repository_name,
            execution_time_seconds=payload.execution_time_seconds,
            start_datetime=payload.start_datetime,
            end_datetime=payload.end_datetime,
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

    return fastapi_app


default_settings = load_settings()
app = create_app(default_settings)
