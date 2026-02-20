import os
import hashlib
import time
from uuid import uuid4
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.infrastructure.fastapi.contact_router import create_contact_router
from src.infrastructure.fastapi.health_router import create_health_router
from src.infrastructure.fastapi.request_metadata import get_client_ip, get_x_forwarded_for
from src.infrastructure.fastapi.tasks_router import create_tasks_router
from src.infrastructure.fastapi.telegram_router import create_telegram_router
from src.infrastructure.rate_limit.in_memory_rate_limiter_gateway import InMemoryRateLimiterGateway
from src.infrastructure.request_id.context_request_id_provider import (
    ContextRequestIdProvider,
    reset_request_id,
    set_request_id,
)
from src.infrastructure.httpx.telegram_api_client import TelegramApiClient
from src.infrastructure.smtp.smtp_mail_gateway import SmtpMailGateway
from src.interface_adapters.controllers.health_controller import HealthController
from src.interface_adapters.controllers.tasks_controller import TasksController
from src.interface_adapters.controllers.telegram_controller import TelegramController
from src.interface_adapters.gateways.file_chat_state_gateway import FileChatStateGateway
from src.interface_adapters.gateways.telegram_notification_gateway import (
    HttpxTelegramNotificationGateway,
)
from src.shared.config import Settings, load_settings, validate_startup_settings
from src.shared.log_safety import mask_identifier
from src.shared.logger import configure_logging, get_logger
from src.use_cases.get_health import GetHealthUseCase
from src.use_cases.get_last_chat import GetLastChatUseCase
from src.use_cases.process_telegram_webhook import ProcessTelegramWebhookUseCase
from src.use_cases.send_mail import SendMailUseCase
from src.use_cases.start_task import StartTaskUseCase
from src.use_cases.submit_contact import SubmitContactUseCase

_SERVICE_NAME = "datamaq-communications-api"

configure_logging()
logger = get_logger(_SERVICE_NAME)

_CONTACT_PATHS = {"/api/contact", "/api/mail", "/contact", "/mail"}
_HEALTH_PATHS = {"/", "/health"}


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


def _payload_fingerprint(raw_body: bytes) -> tuple[int, str]:
    if not raw_body:
        return 0, ""
    return len(raw_body), hashlib.sha256(raw_body).hexdigest()


def _safe_request_id(request: Request, mask_sensitive_ids: bool) -> str:
    request_id = _request_id_from_state(request)
    if not mask_sensitive_ids:
        return request_id
    return mask_identifier(request_id, prefix=3, suffix=3)


def _is_health_path(path: str) -> bool:
    return path in _HEALTH_PATHS


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

    logger.info(
        "Runtime config app_env=%s log_level=%s proxy_headers_enabled=%s forwarded_allow_ips=%s",
        app_settings.app_env,
        app_settings.log_level,
        app_settings.proxy_headers_enabled,
        app_settings.forwarded_allow_ips,
    )
    if app_settings.app_env != "production":
        logger.warning("APP_ENV=%s; se recomienda production en entorno productivo.", app_settings.app_env)


def _build_dependencies(effective_settings: Settings) -> dict[str, Any]:
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
        debug_enabled=effective_settings.debug_telegram_webhook,
        mask_sensitive_ids=effective_settings.mask_sensitive_ids,
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
        mask_sensitive_ids=effective_settings.mask_sensitive_ids,
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
    get_health_use_case = GetHealthUseCase(service_name=_SERVICE_NAME, logger=logger)
    return {
        "send_mail_use_case": send_mail_use_case,
        "submit_contact_use_case": submit_contact_use_case,
        "health_controller": HealthController(get_health_use_case=get_health_use_case),
        "telegram_controller": TelegramController(
            process_webhook_use_case=process_webhook_use_case,
            get_last_chat_use_case=get_last_chat_use_case,
        ),
        "tasks_controller": TasksController(start_task_use_case=start_task_use_case),
        "start_task_use_case": start_task_use_case,
    }


def _register_middlewares(fastapi_app: FastAPI, effective_settings: Settings) -> None:
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

    @fastapi_app.middleware("http")
    async def request_logging_middleware(request: Request, call_next: Any) -> JSONResponse:
        started_at = time.perf_counter()
        client_ip = get_client_ip(request)
        forwarded_for = get_x_forwarded_for(request)
        origin = request.headers.get("Origin", "").strip()
        request_path = request.url.path
        is_health_path = _is_health_path(request_path)

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            logger.exception(
                "request_error",
                extra={
                    "event": "http_request",
                    "request_id": _safe_request_id(request, effective_settings.mask_sensitive_ids),
                    "method": request.method,
                    "path": request_path,
                    "status_code": 500,
                    "duration_ms": duration_ms,
                    "client_ip_real": client_ip,
                    "x_forwarded_for": forwarded_for,
                    "origin": origin,
                },
            )
            raise

        if is_health_path and not effective_settings.http_log_healthchecks:
            return response

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        log_level = logger.debug if is_health_path else logger.info
        log_level(
            "request_completed",
            extra={
                "event": "http_request",
                "request_id": _safe_request_id(request, effective_settings.mask_sensitive_ids),
                "method": request.method,
                "path": request_path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip_real": client_ip,
                "x_forwarded_for": forwarded_for,
                "origin": origin,
            },
        )
        return response


def _register_exception_handlers(fastapi_app: FastAPI, effective_settings: Settings) -> None:
    @fastapi_app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        raw_body = await request.body()
        body_size, body_sha256 = _payload_fingerprint(raw_body)
        logger.error(
            "validation_error",
            extra={
                "event": "validation_error",
                "request_id": _safe_request_id(request, effective_settings.mask_sensitive_ids),
                "method": request.method,
                "path": request.url.path,
                "body_size_bytes": body_size,
                "body_sha256": body_sha256,
                "errors": exc.errors(),
                "origin": request.headers.get("Origin", "").strip(),
            },
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
                    '-H "Content-Type: application/json" '
                    '-d "{\\"duration_seconds\\":2,\\"force_fail\\":false,'
                    '\\"modified_files_count\\":2,'
                    '\\"repository_name\\":\\"datamaq-communications-api\\",'
                    '\\"execution_time_seconds\\":42.5,'
                    '\\"start_datetime\\":\\"2026-02-17T21:34:10Z\\",'
                    '\\"end_datetime\\":\\"2026-02-17T21:35:02Z\\"}"'
                ),
            }

        return JSONResponse(status_code=422, content={"detail": detail})

    @fastapi_app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        logger.warning(
            "http_exception",
            extra={
                "event": "http_exception",
                "request_id": _safe_request_id(request, effective_settings.mask_sensitive_ids),
                "method": request.method,
                "path": request.url.path,
                "status_code": exc.status_code,
                "origin": request.headers.get("Origin", "").strip(),
            },
        )

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


# pylint: disable=too-many-locals,too-many-statements
def create_app(custom_settings: Settings | None = None) -> FastAPI:
    effective_settings = custom_settings or load_settings()
    configure_logging(effective_settings.log_level)
    validate_startup_settings(effective_settings)
    _log_environment_configuration(effective_settings)

    dependencies = _build_dependencies(effective_settings)

    fastapi_app = FastAPI(title="Datamaq Communications API")
    fastapi_app.add_middleware(
        CORSMiddleware,
        allow_origins=list(effective_settings.cors_allowed_origins),
        allow_credentials=False,
        allow_methods=["POST", "OPTIONS"],
        allow_headers=["*"],
    )

    fastapi_app.state.send_mail_use_case = dependencies["send_mail_use_case"]
    fastapi_app.state.submit_contact_use_case = dependencies["submit_contact_use_case"]
    fastapi_app.include_router(create_health_router(dependencies["health_controller"]))
    fastapi_app.include_router(create_telegram_router(dependencies["telegram_controller"]))
    fastapi_app.include_router(
        create_tasks_router(dependencies["tasks_controller"], dependencies["start_task_use_case"])
    )
    fastapi_app.include_router(
        create_contact_router(
            submit_contact_use_case=dependencies["submit_contact_use_case"],
            send_mail_use_case=dependencies["send_mail_use_case"],
            logger=logger,
            debug_observability=effective_settings.debug_contact_observability,
            mask_sensitive_ids=effective_settings.mask_sensitive_ids,
        )
    )
    _register_middlewares(fastapi_app, effective_settings)
    _register_exception_handlers(fastapi_app, effective_settings)

    return fastapi_app


default_settings = load_settings()
settings = default_settings
app = create_app(default_settings)
