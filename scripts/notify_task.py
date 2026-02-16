import argparse
import json
import os
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
    commit_proposal: str,
    repository_name: str,
    execution_time_seconds: float | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "duration_seconds": duration_seconds,
        "force_fail": force_fail,
        "commit_proposal": commit_proposal,
        "repository_name": repository_name,
    }
    if execution_time_seconds is not None:
        payload["execution_time_seconds"] = execution_time_seconds
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
    print(" ".join(command))

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


def parse_args() -> argparse.Namespace:
    default_api_url = os.getenv("TASKS_START_URL", "").strip() or "http://127.0.0.1:8000/tasks/start"
    parser = argparse.ArgumentParser(
        description="Dispara POST /tasks/start con propuesta de commit + repo + tiempo.",
    )
    parser.add_argument(
        "--api-url",
        default=default_api_url,
        help="URL de /tasks/start (default: TASKS_START_URL env o http://127.0.0.1:8000/tasks/start)",
    )
    parser.add_argument(
        "--commit-proposal",
        required=True,
        help="Propuesta de nombre de commit.",
    )
    parser.add_argument(
        "--repository-name",
        default="",
        help="Nombre de repo a reportar (default: detectado por git).",
    )
    parser.add_argument(
        "--execution-time-seconds",
        type=float,
        default=None,
        help="Tiempo real de ejecucion a reportar.",
    )
    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=0.0,
        help="Duracion simulada de tarea en backend (default: 0).",
    )
    parser.add_argument(
        "--force-fail",
        action="store_true",
        help="Fuerza notificacion de fallo en backend.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra el curl pero no envia request.",
    )
    return parser.parse_args()


def main() -> int:
    settings = load_settings()
    args = parse_args()

    commit_proposal = args.commit_proposal.strip()
    if not commit_proposal:
        print("ERROR: --commit-proposal no puede estar vacio.", file=sys.stderr)
        return 2

    repository_name = args.repository_name.strip() or detect_repository_name(settings.repository_name)
    payload = build_payload(
        duration_seconds=args.duration_seconds,
        force_fail=args.force_fail,
        commit_proposal=commit_proposal,
        repository_name=repository_name,
        execution_time_seconds=args.execution_time_seconds,
    )
    return send_task_notification(api_url=args.api_url, payload=payload, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
