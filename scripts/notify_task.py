import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from notify_common import build_payload, default_repository_name, send_task_notification


def parse_args() -> argparse.Namespace:
    default_api_url = os.getenv("TASKS_START_URL", "").strip() or "http://127.0.0.1:8000/tasks/start"
    parser = argparse.ArgumentParser(
        description="Dispara POST /tasks/start con cantidad de archivos modificados + repo + tiempo.",
    )
    parser.add_argument(
        "--api-url",
        default=default_api_url,
        help="URL de /tasks/start (default: TASKS_START_URL env o http://127.0.0.1:8000/tasks/start)",
    )
    parser.add_argument(
        "--modified-files-count",
        type=int,
        required=True,
        help="Cantidad de archivos modificados a reportar.",
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
        "--start-datetime",
        default=None,
        help="Fecha/hora de inicio en UTC ISO 8601. Ej: 2026-02-17T21:34:10Z",
    )
    parser.add_argument(
        "--end-datetime",
        default=None,
        help="Fecha/hora de fin en UTC ISO 8601. Ej: 2026-02-17T21:35:02Z",
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
    args = parse_args()

    modified_files_count = args.modified_files_count
    if modified_files_count < 0:
        print("ERROR: --modified-files-count no puede ser negativo.", file=sys.stderr)
        return 2
    if args.duration_seconds < 0:
        print("ERROR: --duration-seconds no puede ser negativo.", file=sys.stderr)
        return 2
    if args.execution_time_seconds is not None and args.execution_time_seconds < 0:
        print("ERROR: --execution-time-seconds no puede ser negativo.", file=sys.stderr)
        return 2

    repository_name = args.repository_name.strip() or default_repository_name()
    payload = build_payload(
        duration_seconds=args.duration_seconds,
        force_fail=args.force_fail,
        modified_files_count=modified_files_count,
        repository_name=repository_name,
        execution_time_seconds=args.execution_time_seconds,
        start_datetime=args.start_datetime,
        end_datetime=args.end_datetime,
    )
    return send_task_notification(api_url=args.api_url, payload=payload, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
