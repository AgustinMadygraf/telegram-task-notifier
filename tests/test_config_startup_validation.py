from pathlib import Path

import pytest

from src.shared.config import Settings, validate_startup_settings


def _base_settings() -> Settings:
    return Settings(
        project_root=Path("."),
        env_path=Path(".env"),
        state_file_path=Path(".last_chat_id"),
        loaded_env_keys=(),
        server_host="0.0.0.0",
        server_port=8000,
        ngrok_enabled=False,
        ngrok_authtoken="",
        ngrok_domain="",
        auto_set_webhook=False,
        drop_pending_updates=True,
        telegram_webhook_path="/telegram/webhook",
        repository_name="datamaq-communications-api",
        telegram_chat_id=None,
        telegram_token="",
        telegram_webhook_secret="",
        telegram_api_base_url="https://api.telegram.org",
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="",
        smtp_pass="",
        smtp_tls=True,
        smtp_from="no-reply@example.com",
        smtp_to_default="ops@example.com",
        cors_allowed_origins=("https://datamaq.com.ar",),
        app_env="development",
        log_level="INFO",
        proxy_headers_enabled=True,
        forwarded_allow_ips="*",
        rate_limit_window=60,
        rate_limit_max=20,
        honeypot_field="website",
        http_log_healthchecks=False,
        debug_contact_observability=False,
        debug_telegram_webhook=False,
        mask_sensitive_ids=True,
    )


def test_validate_startup_allows_smtp_without_auth() -> None:
    settings = _base_settings()
    validate_startup_settings(settings)


def test_validate_startup_rejects_partial_smtp_auth() -> None:
    settings = _base_settings()
    settings = Settings(**{**settings.__dict__, "smtp_user": "user-only", "smtp_pass": ""})

    with pytest.raises(RuntimeError, match="SMTP_USER and SMTP_PASS"):
        validate_startup_settings(settings)
