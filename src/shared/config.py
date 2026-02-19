import os
from dataclasses import dataclass
from pathlib import Path


def parse_bool(value: str, default: bool) -> bool:
    text = value.strip().lower()
    if not text:
        return default
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def parse_int(value: str, default: int) -> int:
    text = value.strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def parse_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def parse_optional_int(value: str) -> int | None:
    text = value.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def load_env_file(env_path: Path) -> list[str]:
    if not env_path.exists():
        return []

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

    return loaded_keys


@dataclass(frozen=True)
class Settings:  # pylint: disable=too-many-instance-attributes
    project_root: Path
    env_path: Path
    state_file_path: Path
    loaded_env_keys: tuple[str, ...]
    server_host: str
    server_port: int
    ngrok_enabled: bool
    ngrok_authtoken: str
    ngrok_domain: str
    auto_set_webhook: bool
    drop_pending_updates: bool
    telegram_webhook_path: str
    repository_name: str
    telegram_chat_id: int | None
    telegram_token: str
    telegram_webhook_secret: str
    telegram_api_base_url: str
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str
    smtp_tls: bool
    smtp_from: str
    smtp_to_default: str
    cors_allowed_origins: tuple[str, ...]
    app_env: str
    log_level: str
    proxy_headers_enabled: bool
    forwarded_allow_ips: str
    rate_limit_window: int
    rate_limit_max: int
    honeypot_field: str
    http_log_healthchecks: bool
    debug_contact_observability: bool
    debug_telegram_webhook: bool
    mask_sensitive_ids: bool


def validate_startup_settings(settings: Settings) -> None:  # pylint: disable=too-many-branches
    missing_fields: list[str] = []

    if not settings.smtp_host:
        missing_fields.append("SMTP_HOST")
    if settings.smtp_port <= 0:
        missing_fields.append("SMTP_PORT")
    if not settings.smtp_from:
        missing_fields.append("SMTP_FROM")
    if not settings.smtp_to_default:
        missing_fields.append("SMTP_TO_DEFAULT")
    if settings.rate_limit_window <= 0:
        missing_fields.append("RATE_LIMIT_WINDOW")
    if settings.rate_limit_max <= 0:
        missing_fields.append("RATE_LIMIT_MAX")
    if not settings.honeypot_field:
        missing_fields.append("HONEYPOT_FIELD")
    if not settings.cors_allowed_origins:
        missing_fields.append("CORS_ALLOWED_ORIGINS")

    if missing_fields:
        missing = ", ".join(missing_fields)
        raise RuntimeError(f"Missing or invalid critical settings: {missing}")

    valid_envs = {"development", "staging", "production", "test"}
    if settings.app_env not in valid_envs:
        raise RuntimeError(f"APP_ENV invalid: {settings.app_env}")

    if settings.app_env == "production" and "*" in settings.cors_allowed_origins:
        raise RuntimeError("CORS wildcard is not allowed in production")

    if settings.proxy_headers_enabled and not settings.forwarded_allow_ips.strip():
        raise RuntimeError("FORWARDED_ALLOW_IPS is required when PROXY_HEADERS_ENABLED=true")

    has_smtp_user = bool(settings.smtp_user)
    has_smtp_pass = bool(settings.smtp_pass)
    if has_smtp_user != has_smtp_pass:
        raise RuntimeError("SMTP_USER and SMTP_PASS must be both set or both empty")


def load_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    env_path = project_root / ".env"
    loaded_env_keys = load_env_file(env_path)

    return Settings(
        project_root=project_root,
        env_path=env_path,
        state_file_path=project_root / ".last_chat_id",
        loaded_env_keys=tuple(loaded_env_keys),
        server_host=os.getenv("SERVER_HOST", "0.0.0.0").strip() or "0.0.0.0",
        server_port=parse_int(os.getenv("SERVER_PORT", "8000"), 8000),
        ngrok_enabled=parse_bool(os.getenv("NGROK_ENABLED", "true"), True),
        ngrok_authtoken=os.getenv("NGROK_AUTHTOKEN", "").strip(),
        ngrok_domain=os.getenv("NGROK_DOMAIN", "").strip(),
        auto_set_webhook=parse_bool(os.getenv("AUTO_SET_WEBHOOK", "true"), True),
        drop_pending_updates=parse_bool(os.getenv("DROP_PENDING_UPDATES", "true"), True),
        telegram_webhook_path=os.getenv("TELEGRAM_WEBHOOK_PATH", "/telegram/webhook").strip() or "/telegram/webhook",
        repository_name=os.getenv("REPOSITORY_NAME", project_root.name).strip() or project_root.name,
        telegram_chat_id=parse_optional_int(os.getenv("TELEGRAM_CHAT_ID", "")),
        telegram_token=os.getenv("TELEGRAM_TOKEN", "").strip(),
        telegram_webhook_secret=os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip(),
        telegram_api_base_url=os.getenv("TELEGRAM_API_BASE_URL", "https://api.telegram.org").strip(),
        smtp_host=os.getenv("SMTP_HOST", "").strip(),
        smtp_port=parse_int(os.getenv("SMTP_PORT", "587"), 587),
        smtp_user=os.getenv("SMTP_USER", "").strip(),
        smtp_pass=os.getenv("SMTP_PASS", "").strip(),
        smtp_tls=parse_bool(os.getenv("SMTP_TLS", "true"), True),
        smtp_from=os.getenv("SMTP_FROM", "").strip(),
        smtp_to_default=os.getenv("SMTP_TO_DEFAULT", "").strip(),
        cors_allowed_origins=parse_csv(
            os.getenv(
                "CORS_ALLOWED_ORIGINS",
                "https://datamaq.com.ar,https://www.datamaq.com.ar,http://localhost:5173,http://127.0.0.1:5173",
            )
        ),
        app_env=os.getenv("APP_ENV", "development").strip().lower() or "development",
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        proxy_headers_enabled=parse_bool(os.getenv("PROXY_HEADERS_ENABLED", "true"), True),
        forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "*").strip() or "*",
        rate_limit_window=parse_int(os.getenv("RATE_LIMIT_WINDOW", "60"), 60),
        rate_limit_max=parse_int(os.getenv("RATE_LIMIT_MAX", "20"), 20),
        honeypot_field=os.getenv("HONEYPOT_FIELD", "website").strip() or "website",
        http_log_healthchecks=parse_bool(os.getenv("HTTP_LOG_HEALTHCHECKS", "false"), False),
        debug_contact_observability=parse_bool(os.getenv("DEBUG_CONTACT_OBSERVABILITY", "false"), False),
        debug_telegram_webhook=parse_bool(os.getenv("DEBUG_TELEGRAM_WEBHOOK", "false"), False),
        mask_sensitive_ids=parse_bool(os.getenv("MASK_SENSITIVE_IDS", "true"), True),
    )
