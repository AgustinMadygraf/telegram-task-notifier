import threading
import time

import httpx
import uvicorn

from src.infrastructure.fastapi.app import app, logger, settings
from src.infrastructure.httpx.telegram_webhook_client import TelegramWebhookClient


def _normalize_webhook_path(path: str) -> str:
    clean = path.strip()
    if not clean:
        return "/telegram/webhook"
    if not clean.startswith("/"):
        return f"/{clean}"
    return clean


def _wait_for_server_started(
    server: uvicorn.Server, server_thread: threading.Thread, timeout_seconds: float = 20.0
) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        if server.started:
            return True
        if not server_thread.is_alive():
            return False
        time.sleep(0.2)
    return False


def _configure_telegram_webhook(public_base_url: str) -> None:
    if not settings.auto_set_webhook:
        logger.info("AUTO_SET_WEBHOOK=false. Se omite configuracion automatica.")
        return

    if not settings.telegram_token:
        logger.warning("TELEGRAM_TOKEN no configurado. Se omite setWebhook.")
        return

    webhook_path = _normalize_webhook_path(settings.telegram_webhook_path)
    webhook_url = f"{public_base_url}{webhook_path}"
    client = TelegramWebhookClient(
        telegram_token=settings.telegram_token,
        telegram_api_base_url=settings.telegram_api_base_url,
    )

    logger.info("Configurando webhook en %s", webhook_url)
    try:
        set_result = client.set_webhook(
            webhook_url=webhook_url,
            secret_token=settings.telegram_webhook_secret or None,
            drop_pending_updates=settings.drop_pending_updates,
        )
        if not set_result.get("ok"):
            logger.error("setWebhook devolvio error: %s", set_result)
            return

        info_result = client.get_webhook_info()
        if not info_result.get("ok"):
            logger.error("getWebhookInfo devolvio error: %s", info_result)
            return

        info = info_result.get("result", {})
        logger.info("Webhook configurado. pending_update_count=%s", info.get("pending_update_count"))
        if info.get("last_error_message"):
            logger.warning("Telegram webhook last_error_message=%s", info.get("last_error_message"))
    except httpx.HTTPError:
        logger.exception("Error HTTP configurando webhook de Telegram")


def main() -> int:
    logger.info("Iniciando servidor unico con ngrok + webhook automatico")
    logger.info("Config server: host=%s port=%s", settings.server_host, settings.server_port)

    config = uvicorn.Config(
        app=app,
        host=settings.server_host,
        port=settings.server_port,
        log_level=settings.log_level.lower(),
        proxy_headers=settings.proxy_headers_enabled,
        forwarded_allow_ips=settings.forwarded_allow_ips,
    )
    server = uvicorn.Server(config)

    server_thread = threading.Thread(target=server.run, name="uvicorn-server", daemon=True)
    server_thread.start()

    if not _wait_for_server_started(server, server_thread):
        logger.error("El servidor no estuvo listo a tiempo. Abortando.")
        server.should_exit = True
        server_thread.join(timeout=5.0)
        return 1

    logger.info("Servidor listo en http://127.0.0.1:%s", settings.server_port)

    ngrok_service = None
    try:
        if settings.ngrok_enabled:
            try:
                from src.infrastructure.pyngrok.ngrok_service import NgrokService
            except ModuleNotFoundError:
                logger.error("No se encontro pyngrok. Instala dependencia: pip install pyngrok")
                server.should_exit = True
                server_thread.join(timeout=5.0)
                return 1

            ngrok_service = NgrokService(auth_token=settings.ngrok_authtoken)
            public_url = ngrok_service.start_http_tunnel(
                port=settings.server_port,
                domain=settings.ngrok_domain,
            )
            logger.info("Tunnel ngrok activo: %s", public_url)
            _configure_telegram_webhook(public_url)
        else:
            logger.info("NGROK_ENABLED=false. Se omite tunel ngrok.")
    except Exception:
        logger.exception("Fallo inicializando ngrok y/o webhook")
        server.should_exit = True
        server_thread.join(timeout=5.0)
        return 1

    try:
        while server_thread.is_alive():
            server_thread.join(timeout=0.5)
    except KeyboardInterrupt:
        logger.info("Interrupcion recibida. Cerrando servicios...")
    finally:
        if ngrok_service is not None:
            ngrok_service.stop()
        server.should_exit = True
        server_thread.join(timeout=10.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
