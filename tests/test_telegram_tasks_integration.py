import os
from pathlib import Path

from fastapi.testclient import TestClient

from src.shared.config import Settings, load_settings


def _configure_env() -> None:
    os.environ["APP_ENV"] = "development"
    os.environ["SMTP_HOST"] = "localhost"
    os.environ["SMTP_PORT"] = "2525"
    os.environ["SMTP_USER"] = ""
    os.environ["SMTP_PASS"] = ""
    os.environ["SMTP_TLS"] = "false"
    os.environ["SMTP_FROM"] = "no-reply@datamaq.com.ar"
    os.environ["SMTP_TO_DEFAULT"] = "ops@datamaq.com.ar"
    os.environ["CORS_ALLOWED_ORIGINS"] = "https://datamaq.com.ar"
    os.environ["RATE_LIMIT_WINDOW"] = "60"
    os.environ["RATE_LIMIT_MAX"] = "20"
    os.environ["HONEYPOT_FIELD"] = "website"
    os.environ["TELEGRAM_TOKEN"] = ""


def _settings_for_test(
    tmp_path: Path,
    *,
    fallback_chat_id: int | None,
    webhook_secret: str,
) -> Settings:
    _configure_env()
    os.environ["TELEGRAM_CHAT_ID"] = "" if fallback_chat_id is None else str(fallback_chat_id)
    os.environ["TELEGRAM_WEBHOOK_SECRET"] = webhook_secret
    settings = load_settings()
    return Settings(
        **{
            **settings.__dict__,
            "state_file_path": tmp_path / ".last_chat_id",
            "telegram_chat_id": fallback_chat_id,
            "telegram_webhook_secret": webhook_secret,
        }
    )


def _client(settings: Settings) -> TestClient:
    from src.infrastructure.fastapi.app import create_app

    app = create_app(settings)
    return TestClient(app)


def test_telegram_webhook_updates_last_chat_and_last_chat_endpoint(tmp_path) -> None:
    settings = _settings_for_test(tmp_path, fallback_chat_id=None, webhook_secret="secret-123")

    with _client(settings) as api_client:
        response = api_client.post(
            "/telegram/webhook",
            json={"update_id": 1, "message": {"chat": {"id": 888}}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "secret-123"},
        )
        last_chat_response = api_client.get("/telegram/last_chat")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "captured_chat_id": 888}
    assert last_chat_response.status_code == 200
    assert last_chat_response.json() == {"last_chat_id": 888}


def test_telegram_webhook_rejects_invalid_secret(tmp_path) -> None:
    settings = _settings_for_test(tmp_path, fallback_chat_id=None, webhook_secret="expected-secret")

    with _client(settings) as api_client:
        response = api_client.post(
            "/telegram/webhook",
            json={"update_id": 2, "message": {"chat": {"id": 999}}},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid Telegram secret token"


def test_tasks_start_returns_400_when_chat_id_is_missing(tmp_path) -> None:
    settings = _settings_for_test(tmp_path, fallback_chat_id=None, webhook_secret="")

    with _client(settings) as api_client:
        response = api_client.post(
            "/tasks/start",
            json={"duration_seconds": 0.0, "force_fail": False, "modified_files_count": 0},
        )

    assert response.status_code == 400
    assert "last_chat_id es null" in response.json()["detail"]


def test_tasks_start_returns_started_with_fallback_chat_id(tmp_path) -> None:
    settings = _settings_for_test(tmp_path, fallback_chat_id=555, webhook_secret="")

    with _client(settings) as api_client:
        response = api_client.post(
            "/tasks/start",
            json={"duration_seconds": 0.0, "force_fail": False, "modified_files_count": 2},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "started"
    assert response.json()["chat_id"] == 555


def test_tasks_start_validation_error_contains_cmd_hint(tmp_path) -> None:
    settings = _settings_for_test(tmp_path, fallback_chat_id=555, webhook_secret="")

    with _client(settings) as api_client:
        response = api_client.post(
            "/tasks/start",
            content="{invalid-json",
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "errors" in detail
    assert "hint" in detail
