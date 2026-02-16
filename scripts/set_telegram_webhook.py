import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx

from get_ngrok_url import resolve_ngrok_https_url


def mask_token(token: str) -> str:
    if len(token) <= 10:
        return "***"
    return f"{token[:6]}...{token[-4:]}"


def load_env_file() -> None:
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        print(f"[env] No se encontro .env en: {env_path}")
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
        print(f"[env] .env cargado. Variables inyectadas: {', '.join(loaded_keys)}")
    else:
        print("[env] .env encontrado, sin variables nuevas para inyectar.")


def parse_bool_env(value: str | None, default: bool) -> bool:
    if value is None or not value.strip():
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(
        f"Valor booleano invalido '{value}' para DROP_PENDING_UPDATES. "
        "Usa true/false."
    )


def build_webhook_url(base_url: str) -> str:
    clean_base = base_url.strip().rstrip("/")
    if not clean_base:
        raise ValueError("La URL base del webhook esta vacia.")
    return f"{clean_base}/telegram/webhook"


def resolve_base_url_from_env() -> str:
    webhook_url_env = os.getenv("WEBHOOK_URL", "").strip()
    if webhook_url_env:
        print(f"[webhook] Usando WEBHOOK_URL desde entorno: {webhook_url_env.rstrip('/')}")
        return webhook_url_env.rstrip("/")
    print("[webhook] WEBHOOK_URL no definido, resolviendo URL HTTPS desde ngrok local...")
    return resolve_ngrok_https_url()


def configure_telegram_webhook(
    token: str,
    webhook_url: str,
    secret_token: str | None,
    drop_pending_updates: bool,
) -> dict[str, Any]:
    base = f"https://api.telegram.org/bot{token}"
    set_webhook_endpoint = f"{base}/setWebhook"
    webhook_info_endpoint = f"{base}/getWebhookInfo"
    masked_base = f"https://api.telegram.org/bot{mask_token(token)}"

    payload: dict[str, Any] = {
        "url": webhook_url,
        "drop_pending_updates": str(drop_pending_updates).lower(),
    }
    if secret_token:
        payload["secret_token"] = secret_token

    print(f"[telegram] setWebhook endpoint: {masked_base}/setWebhook")
    print(
        "[telegram] setWebhook payload: "
        f"url={webhook_url} drop_pending_updates={payload['drop_pending_updates']} "
        f"secret_token={'si' if bool(secret_token) else 'no'}"
    )

    try:
        with httpx.Client(timeout=20.0) as client:
            set_response = client.post(set_webhook_endpoint, data=payload)
            print(f"[telegram] setWebhook HTTP {set_response.status_code}")
            set_response.raise_for_status()
            set_result = set_response.json()
            print(f"[telegram] setWebhook respuesta: {set_result}")

            if not set_result.get("ok"):
                raise RuntimeError(
                    f"Telegram setWebhook devolvio error: {set_result.get('description', set_result)}"
                )

            info_response = client.get(webhook_info_endpoint)
            print(f"[telegram] getWebhookInfo HTTP {info_response.status_code}")
            info_response.raise_for_status()
            info_result = info_response.json()
            print(f"[telegram] getWebhookInfo respuesta ok={info_result.get('ok')}")

            if not info_result.get("ok"):
                raise RuntimeError(
                    f"Telegram getWebhookInfo devolvio error: {info_result.get('description', info_result)}"
                )
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Error HTTP llamando a Telegram API: {exc}") from exc
    except ValueError as exc:
        raise RuntimeError(f"Respuesta no JSON de Telegram API: {exc}") from exc

    return {
        "set_webhook": set_result,
        "webhook_info": info_result.get("result", {}),
    }


def main() -> None:
    print("[setup] Iniciando set_telegram_webhook.py")
    load_env_file()

    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    if not token:
        print("ERROR: TELEGRAM_TOKEN es obligatorio.", file=sys.stderr)
        raise SystemExit(1)
    print(f"[setup] TELEGRAM_TOKEN detectado: {mask_token(token)}")

    secret_token = os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip() or None
    print(f"[setup] TELEGRAM_WEBHOOK_SECRET configurado: {'si' if bool(secret_token) else 'no'}")

    try:
        drop_pending_updates = parse_bool_env(
            os.getenv("DROP_PENDING_UPDATES"),
            default=True,
        )
        print(f"[setup] DROP_PENDING_UPDATES={drop_pending_updates}")
        base_url = resolve_base_url_from_env()
        print(f"[setup] base_url resuelto: {base_url}")
        webhook_url = build_webhook_url(base_url)
        print(f"[setup] webhook_url final: {webhook_url}")
        result = configure_telegram_webhook(
            token=token,
            webhook_url=webhook_url,
            secret_token=secret_token,
            drop_pending_updates=drop_pending_updates,
        )
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)

    print(f"Webhook configurado en: {webhook_url}")
    print("getWebhookInfo:")
    print(json.dumps(result["webhook_info"], indent=2, ensure_ascii=False))

    last_error_message = result["webhook_info"].get("last_error_message")
    if last_error_message:
        print(
            f"Advertencia: last_error_message={last_error_message}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
