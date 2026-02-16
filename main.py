import asyncio
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram-task-notifier")

app = FastAPI(title="Telegram Task Notifier MVP")

_state_lock = threading.Lock()
_last_chat_id: Optional[int] = None
_state_file_path = Path(__file__).resolve().parent / ".last_chat_id"


def _load_env_file() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        logger.info("No se encontro .env en %s", env_path)
        return

    loaded_keys: list[str] = []
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
            loaded_keys.append(key)

    if loaded_keys:
        logger.info(".env cargado. Variables inyectadas: %s", ", ".join(loaded_keys))
    else:
        logger.info(".env encontrado, pero no se inyecto ninguna variable nueva.")


_load_env_file()


class TaskStartRequest(BaseModel):
    duration_seconds: float = Field(default=1.0, ge=0.0, le=600.0)
    force_fail: bool = False


def _get_last_chat_id() -> Optional[int]:
    with _state_lock:
        return _last_chat_id


def _load_last_chat_id_from_file() -> None:
    global _last_chat_id
    if not _state_file_path.exists():
        logger.info("No se encontro archivo de estado de chat en %s", _state_file_path)
        return

    try:
        raw_value = _state_file_path.read_text(encoding="utf-8").strip()
        if not raw_value:
            logger.warning("Archivo de estado vacio en %s", _state_file_path)
            return

        chat_id = int(raw_value)
    except ValueError:
        logger.warning("Archivo de estado invalido en %s", _state_file_path)
        return
    except OSError:
        logger.exception("No se pudo leer archivo de estado en %s", _state_file_path)
        return

    with _state_lock:
        _last_chat_id = chat_id
    logger.info("last_chat_id restaurado desde archivo: %s", chat_id)


def _persist_last_chat_id(chat_id: int) -> None:
    temp_path = _state_file_path.with_suffix(".tmp")
    try:
        temp_path.write_text(str(chat_id), encoding="utf-8")
        temp_path.replace(_state_file_path)
        logger.info("last_chat_id persistido en archivo: %s", chat_id)
    except OSError:
        logger.exception("No se pudo persistir last_chat_id en %s", _state_file_path)


def _set_last_chat_id(chat_id: int) -> None:
    global _last_chat_id
    with _state_lock:
        _last_chat_id = chat_id
    _persist_last_chat_id(chat_id)


_load_last_chat_id_from_file()


def _extract_chat_id(update: dict[str, Any]) -> Optional[int]:
    message = update.get("message") or update.get("edited_message")
    if isinstance(message, dict):
        chat = message.get("chat")
        if isinstance(chat, dict) and isinstance(chat.get("id"), int):
            return chat["id"]

    callback_query = update.get("callback_query")
    if isinstance(callback_query, dict):
        message = callback_query.get("message")
        if isinstance(message, dict):
            chat = message.get("chat")
            if isinstance(chat, dict) and isinstance(chat.get("id"), int):
                return chat["id"]

    return None


async def _send_telegram_message(chat_id: int, text: str) -> None:
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    if not token:
        logger.error("TELEGRAM_TOKEN no configurado. No se puede enviar mensaje.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    logger.info("Enviando mensaje a Telegram. chat_id=%s text=%s", chat_id, text)

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            logger.info("Respuesta Telegram sendMessage status=%s", response.status_code)
            if not data.get("ok"):
                logger.error("Telegram API devolvio error: %s", data)
            else:
                logger.info("Mensaje enviado correctamente. message_id=%s", data.get("result", {}).get("message_id"))
    except httpx.HTTPError:
        logger.exception("Error llamando a Telegram sendMessage")


async def _run_task_and_notify(chat_id: int, duration_seconds: float, force_fail: bool) -> None:
    logger.info(
        "Tarea iniciada. chat_id=%s duration_seconds=%s force_fail=%s",
        chat_id,
        duration_seconds,
        force_fail,
    )
    try:
        await asyncio.sleep(duration_seconds)
        logger.info("Tarea finalizo espera. chat_id=%s", chat_id)
        if force_fail:
            raise RuntimeError("Falla forzada para prueba MVP.")
        await _send_telegram_message(chat_id, "Termin\u00e9")
    except Exception:
        logger.exception("La tarea fallo.")
        await _send_telegram_message(chat_id, "Fall\u00f3")


@app.post("/telegram/webhook")
async def telegram_webhook(
    update: dict[str, Any],
    x_telegram_bot_api_secret_token: Optional[str] = Header(default=None),
) -> dict[str, Any]:
    logger.info(
        "Webhook recibido. update_id=%s has_secret_header=%s",
        update.get("update_id"),
        bool(x_telegram_bot_api_secret_token),
    )
    expected_secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
    if expected_secret and x_telegram_bot_api_secret_token != expected_secret:
        logger.warning("Webhook rechazado por secret invalido.")
        raise HTTPException(status_code=403, detail="Invalid Telegram secret token")

    chat_id = _extract_chat_id(update)
    if chat_id is not None:
        _set_last_chat_id(chat_id)
        logger.info("last_chat_id actualizado: %s", chat_id)
    else:
        logger.info("Webhook sin chat_id extraible. keys=%s", list(update.keys()))

    return {"ok": True, "captured_chat_id": chat_id}


@app.get("/telegram/last_chat")
async def telegram_last_chat() -> dict[str, Any]:
    logger.info("Consulta last_chat_id -> %s", _get_last_chat_id())
    return {"last_chat_id": _get_last_chat_id()}


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
                "-d \"{\\\"duration_seconds\\\":2,\\\"force_fail\\\":false}\""
            ),
        }

    return JSONResponse(status_code=422, content={"detail": detail})


@app.post("/tasks/start")
async def tasks_start(
    payload: TaskStartRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, Any]:
    logger.info(
        "POST /tasks/start payload=%s",
        json.dumps(payload.model_dump(), ensure_ascii=False),
    )
    chat_id = _get_last_chat_id()
    if chat_id is None:
        raise HTTPException(
            status_code=400,
            detail="last_chat_id es null. Escribile al bot primero para capturarlo.",
        )

    logger.info("Programando tarea para chat_id=%s", chat_id)
    background_tasks.add_task(
        _run_task_and_notify,
        chat_id,
        payload.duration_seconds,
        payload.force_fail,
    )
    return {
        "status": "started",
        "chat_id": chat_id,
        "duration_seconds": payload.duration_seconds,
        "force_fail": payload.force_fail,
    }
