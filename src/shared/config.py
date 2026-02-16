import os
from dataclasses import dataclass
from pathlib import Path


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
class Settings:
    project_root: Path
    env_path: Path
    state_file_path: Path
    loaded_env_keys: tuple[str, ...]
    repository_name: str
    telegram_chat_id: int | None
    telegram_token: str
    telegram_webhook_secret: str
    telegram_api_base_url: str


def load_settings() -> Settings:
    project_root = Path(__file__).resolve().parents[2]
    env_path = project_root / ".env"
    loaded_env_keys = load_env_file(env_path)

    return Settings(
        project_root=project_root,
        env_path=env_path,
        state_file_path=project_root / ".last_chat_id",
        loaded_env_keys=tuple(loaded_env_keys),
        repository_name=os.getenv("REPOSITORY_NAME", project_root.name).strip() or project_root.name,
        telegram_chat_id=parse_optional_int(os.getenv("TELEGRAM_CHAT_ID", "")),
        telegram_token=os.getenv("TELEGRAM_TOKEN", "").strip(),
        telegram_webhook_secret=os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip(),
        telegram_api_base_url=os.getenv("TELEGRAM_API_BASE_URL", "https://api.telegram.org").strip(),
    )
