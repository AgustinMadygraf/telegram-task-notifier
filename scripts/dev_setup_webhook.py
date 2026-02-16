import json
import os
import sys

from get_ngrok_url import resolve_ngrok_https_url
from set_telegram_webhook import (
    build_webhook_url,
    configure_telegram_webhook,
    load_env_file,
    mask_token,
    parse_bool_env,
)


def main() -> None:
    print("[dev-setup] Iniciando flujo de setup webhook para desarrollo")
    load_env_file()

    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    if not token:
        print("ERROR: TELEGRAM_TOKEN es obligatorio.", file=sys.stderr)
        raise SystemExit(1)
    print(f"[dev-setup] TELEGRAM_TOKEN detectado: {mask_token(token)}")

    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip() or None
    print(f"[dev-setup] TELEGRAM_WEBHOOK_SECRET configurado: {'si' if bool(secret) else 'no'}")

    try:
        print("[dev-setup] Leyendo DROP_PENDING_UPDATES...")
        drop_pending_updates = parse_bool_env(
            os.getenv("DROP_PENDING_UPDATES"),
            default=True,
        )
        print(f"[dev-setup] DROP_PENDING_UPDATES={drop_pending_updates}")

        env_webhook_url = os.getenv("WEBHOOK_URL", "").strip()
        if env_webhook_url:
            print(f"[dev-setup] WEBHOOK_URL definido en entorno: {env_webhook_url}")
            base_url = env_webhook_url
        else:
            print("[dev-setup] WEBHOOK_URL no definido. Consultando ngrok local...")
            base_url = resolve_ngrok_https_url()
            print(f"[dev-setup] URL HTTPS de ngrok detectada: {base_url}")

        webhook_url = build_webhook_url(base_url)
        print(f"[dev-setup] Webhook final a registrar: {webhook_url}")

        print("[dev-setup] Ejecutando setWebhook + getWebhookInfo...")
        result = configure_telegram_webhook(
            token=token,
            webhook_url=webhook_url,
            secret_token=secret,
            drop_pending_updates=drop_pending_updates,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

    print(f"Webhook configurado: {webhook_url}")
    print("getWebhookInfo:")
    print(json.dumps(result["webhook_info"], indent=2, ensure_ascii=False))
    print()
    print("Prueba MVP:")
    print("1) Manda 'hola' al bot en Telegram.")
    print("2) Verifica: GET http://127.0.0.1:8000/telegram/last_chat")
    print("3) Proba /tasks/start desde PowerShell:")
    print(
        "   Invoke-RestMethod -Method POST -Uri http://127.0.0.1:8000/tasks/start "
        "-ContentType 'application/json' "
        "-Body '{\"duration_seconds\":2,\"force_fail\":false,"
        "\"commit_proposal\":\"feat: notificar tiempo y resumen por telegram\"}'"
    )
    print("4) Proba /tasks/start desde CMD:")
    print(
        "   curl -X POST http://127.0.0.1:8000/tasks/start "
        "-H \"Content-Type: application/json\" "
        "-d \"{\\\"duration_seconds\\\":2,\\\"force_fail\\\":false,"
        "\\\"commit_proposal\\\":\\\"feat: notificar tiempo y resumen por telegram\\\"}\""
    )
    print("5) Confirma que el bot envie 'Termin\u00e9' (o 'Fall\u00f3' si forzas error).")


if __name__ == "__main__":
    main()
