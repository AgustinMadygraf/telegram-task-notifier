import os
from contextlib import contextmanager
from typing import Iterator

from fastapi.testclient import TestClient

from src.shared.config import load_settings

CONTACT_PATH = "/api/contact"
MAIL_PATH = "/api/mail"
LEGACY_CONTACT_PATH = "/contact"
LEGACY_MAIL_PATH = "/mail"


def _configure_env() -> None:
    os.environ["APP_ENV"] = "development"
    os.environ["SMTP_HOST"] = "localhost"
    os.environ["SMTP_PORT"] = "2525"
    os.environ["SMTP_USER"] = ""
    os.environ["SMTP_PASS"] = ""
    os.environ["SMTP_TLS"] = "false"
    os.environ["SMTP_FROM"] = "no-reply@datamaq.com.ar"
    os.environ["SMTP_TO_DEFAULT"] = "ops@datamaq.com.ar"
    os.environ["CORS_ALLOWED_ORIGINS"] = (
        "https://datamaq.com.ar,https://www.datamaq.com.ar,http://localhost:5173,http://127.0.0.1:5173"
    )
    os.environ["RATE_LIMIT_WINDOW"] = "60"
    os.environ["RATE_LIMIT_MAX"] = "1"
    os.environ["HONEYPOT_FIELD"] = "website"


@contextmanager
def _client() -> Iterator[TestClient]:
    _configure_env()
    from src.infrastructure.fastapi.app import create_app

    settings = load_settings()
    app = create_app(settings)
    app.state.send_mail_use_case.execute = lambda *args, **kwargs: None

    with TestClient(app) as test_client:
        yield test_client


def _valid_payload() -> dict[str, object]:
    return {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "message": "Quiero una demo",
        "meta": {"source": "landing"},
        "attribution": {
            "path": "/contacto",
            "referrer": "https://google.com",
            "user_agent": "pytest",
            "website": "",
        },
    }


def test_health_endpoints_return_ok() -> None:
    with _client() as api_client:
        root_response = api_client.get("/")
        health_response = api_client.get("/health")

    assert root_response.status_code == 200
    assert health_response.status_code == 200
    assert root_response.json()["status"] == "ok"
    assert health_response.json() == root_response.json()


def test_contact_returns_202() -> None:
    with _client() as api_client:
        response = api_client.post(CONTACT_PATH, json=_valid_payload())

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "accepted"
    assert body["request_id"]
    assert response.headers.get("x-request-id")


def test_mail_returns_202() -> None:
    payload = _valid_payload()
    payload["email"] = "other@example.com"

    with _client() as api_client:
        response = api_client.post(MAIL_PATH, json=payload)

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


def test_contact_returns_422_on_invalid_schema() -> None:
    payload = _valid_payload()
    payload["email"] = "invalid-email"

    with _client() as api_client:
        response = api_client.post(CONTACT_PATH, json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["request_id"]


def test_contact_returns_400_on_honeypot() -> None:
    payload = _valid_payload()
    payload["attribution"]["website"] = "I am a bot"

    with _client() as api_client:
        response = api_client.post(CONTACT_PATH, json=payload)

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"] == "BAD_REQUEST"


def test_contact_returns_429_when_rate_limited() -> None:
    with _client() as api_client:
        first = api_client.post(CONTACT_PATH, json=_valid_payload())
        second = api_client.post(CONTACT_PATH, json=_valid_payload())

    assert first.status_code == 202
    assert second.status_code == 429
    body = second.json()
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"


def test_contact_returns_500_on_unexpected_error() -> None:
    with _client() as api_client:
        original_submit = api_client.app.state.submit_contact_use_case.submit

        def _broken_submit(*args: object, **kwargs: object) -> object:
            raise RuntimeError("boom")

        api_client.app.state.submit_contact_use_case.submit = _broken_submit
        response = api_client.post(CONTACT_PATH, json=_valid_payload())
        api_client.app.state.submit_contact_use_case.submit = original_submit

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert body["request_id"]


def test_legacy_paths_remain_compatible() -> None:
    with _client() as api_client:
        contact_response = api_client.post(LEGACY_CONTACT_PATH, json=_valid_payload())
        mail_response = api_client.post(LEGACY_MAIL_PATH, json=_valid_payload())

    assert contact_response.status_code == 202
    assert mail_response.status_code == 202


def test_cors_preflight_allows_required_origins() -> None:
    required_origins = [
        "https://datamaq.com.ar",
        "https://www.datamaq.com.ar",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    with _client() as api_client:
        for origin in required_origins:
            response = api_client.options(
                CONTACT_PATH,
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                },
            )
            assert response.status_code == 200
            assert response.headers.get("access-control-allow-origin") == origin
            assert response.headers.get("access-control-allow-methods") == "POST, OPTIONS"


def test_options_probe_without_preflight_headers_returns_204() -> None:
    with _client() as api_client:
        for path in [CONTACT_PATH, MAIL_PATH]:
            response = api_client.options(path, headers={"Origin": "https://datamaq.com.ar"})
            assert response.status_code == 204
            assert response.headers.get("access-control-allow-origin") == "https://datamaq.com.ar"
            assert response.headers.get("access-control-allow-methods") == "POST, OPTIONS"
