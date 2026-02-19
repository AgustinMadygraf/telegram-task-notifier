from pathlib import Path

import pytest

from src.shared.config import (
    Settings,
    load_env_file,
    parse_bool,
    parse_int,
    parse_optional_int,
    validate_startup_settings,
)


def _valid_settings() -> Settings:
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
        rate_limit_window=60,
        rate_limit_max=20,
        honeypot_field="website",
    )


def test_parse_helpers_cover_default_and_invalid_paths() -> None:
    assert parse_bool("", default=True) is True
    assert parse_bool("invalid", default=False) is False
    assert parse_int("", default=8) == 8
    assert parse_int("abc", default=8) == 8
    assert parse_optional_int("") is None
    assert parse_optional_int("nan") is None


def test_load_env_file_returns_empty_when_file_is_missing(tmp_path) -> None:
    missing_file = tmp_path / ".env.missing"

    assert load_env_file(missing_file) == []


def test_load_env_file_ignores_comments_and_invalid_rows(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\nINVALID_LINE\n\nKEY=value\n", encoding="utf-8")

    loaded = load_env_file(env_file)

    assert "KEY" in loaded


def test_validate_startup_settings_reports_missing_critical_values() -> None:
    settings = _valid_settings()
    broken = Settings(
        **{
            **settings.__dict__,
            "smtp_host": "",
            "smtp_port": 0,
            "smtp_from": "",
            "smtp_to_default": "",
            "rate_limit_window": 0,
            "rate_limit_max": 0,
            "honeypot_field": "",
            "cors_allowed_origins": (),
        }
    )

    with pytest.raises(RuntimeError, match="Missing or invalid critical settings"):
        validate_startup_settings(broken)


def test_validate_startup_settings_rejects_invalid_app_env() -> None:
    settings = _valid_settings()
    broken = Settings(**{**settings.__dict__, "app_env": "qa"})

    with pytest.raises(RuntimeError, match="APP_ENV invalid"):
        validate_startup_settings(broken)


def test_validate_startup_settings_rejects_wildcard_cors_in_production() -> None:
    settings = _valid_settings()
    broken = Settings(**{**settings.__dict__, "app_env": "production", "cors_allowed_origins": ("*",)})

    with pytest.raises(RuntimeError, match="CORS wildcard is not allowed in production"):
        validate_startup_settings(broken)
