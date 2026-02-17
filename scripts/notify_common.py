import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.shared.config import load_settings


def detect_repository_name(default_name: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            root_path = result.stdout.strip()
            if root_path:
                return Path(root_path).name
    except Exception:
        pass

    return default_name


def resolve_curl_binary() -> str:
    for candidate in ("curl.exe", "curl"):
        found = shutil.which(candidate)
        if found:
            return found
    raise RuntimeError("No se encontro curl en PATH.")


def build_payload(
    duration_seconds: float,
    force_fail: bool,
    modified_files_count: int,
    repository_name: str,
    execution_time_seconds: float | None,
    start_datetime: str | None = None,
    end_datetime: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "duration_seconds": duration_seconds,
        "force_fail": force_fail,
        "modified_files_count": modified_files_count,
        "repository_name": repository_name,
    }
    if execution_time_seconds is not None:
        payload["execution_time_seconds"] = execution_time_seconds
    if start_datetime:
        payload["start_datetime"] = start_datetime
    if end_datetime:
        payload["end_datetime"] = end_datetime
    return payload


def send_task_notification(
    api_url: str,
    payload: dict[str, object],
    dry_run: bool = False,
) -> int:
    body = json.dumps(payload, ensure_ascii=False)
    curl_bin = resolve_curl_binary()
    command = [
        curl_bin,
        "-sS",
        "-X",
        "POST",
        api_url,
        "-H",
        "Content-Type: application/json",
        "-d",
        body,
    ]

    print("[notify] curl command:")
    print(" ".join(shlex.quote(part) for part in command))

    if dry_run:
        print("[notify] dry-run activo. No se envia request.")
        return 0

    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)

    return result.returncode


def default_repository_name() -> str:
    settings = load_settings()
    return detect_repository_name(settings.repository_name)
