import argparse
import fnmatch
import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from notify_task import build_payload, detect_repository_name, send_task_notification
from src.shared.config import load_settings

DEFAULT_OPERATIONAL_EXCLUDE_PATTERNS = (
    "*.log",
    "*.tmp",
    "*.temp",
    ".last_chat_id",
    ".last_chat_id.tmp",
)


def _git_paths(args: list[str]) -> list[str] | None:
    try:
        result = subprocess.run(
            ["git", *args, "-z"],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
        )
    except (FileNotFoundError, OSError):
        return None

    if result.returncode != 0:
        return None

    output = result.stdout
    if not output:
        return []
    return [item.decode("utf-8", errors="surrogateescape") for item in output.split(b"\x00") if item]


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_exclude_patterns(raw_patterns: str) -> list[str]:
    if not raw_patterns.strip():
        return list(DEFAULT_OPERATIONAL_EXCLUDE_PATTERNS)
    return [part.strip() for part in raw_patterns.split(",") if part.strip()]


def should_exclude_path(path_str: str, exclude_patterns: list[str]) -> bool:
    normalized = path_str.replace("\\", "/")
    name = Path(normalized).name
    for pattern in exclude_patterns:
        candidate = pattern.replace("\\", "/")
        if fnmatch.fnmatch(normalized, candidate) or fnmatch.fnmatch(name, candidate):
            return True
    return False


def get_working_tree_snapshot(exclude_patterns: list[str]) -> tuple[dict[str, str] | None, int]:
    tracked_files = _git_paths(["ls-files"])
    if tracked_files is None:
        return None, 0

    untracked_files = _git_paths(["ls-files", "--others", "--exclude-standard"])
    if untracked_files is None:
        return None, 0

    snapshot: dict[str, str] = {}
    excluded_count = 0
    for path_str in sorted(set(tracked_files + untracked_files)):
        if should_exclude_path(path_str, exclude_patterns):
            excluded_count += 1
            continue
        full_path = PROJECT_ROOT / path_str
        if not full_path.exists() or not full_path.is_file():
            snapshot[path_str] = "<missing>"
            continue

        try:
            digest = _sha256_file(full_path)
        except OSError:
            snapshot[path_str] = "<unreadable>"
            continue
        snapshot[path_str] = digest

    return snapshot, excluded_count


def get_changed_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    changed: list[str] = []
    all_paths = sorted(set(before.keys()) | set(after.keys()))
    for path in all_paths:
        if before.get(path) != after.get(path):
            changed.append(path)
    return changed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ejecuta Codex CLI y luego notifica /tasks/start automaticamente.",
    )
    parser.add_argument(
        "--repository-name",
        default="",
        help="Nombre de repo a reportar (default: detectado por git).",
    )
    parser.add_argument(
        "--api-url",
        default=os.getenv("TASKS_START_URL", "").strip() or "http://127.0.0.1:8000/tasks/start",
        help="URL de /tasks/start (default: TASKS_START_URL env o http://127.0.0.1:8000/tasks/start).",
    )
    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=0.0,
        help="Duracion simulada de tarea en backend (default: 0).",
    )
    parser.add_argument(
        "--on-git-error",
        choices=("notify", "skip"),
        default="notify",
        help="Si falla la lectura de git status: notify (default) o skip.",
    )
    parser.add_argument(
        "--dry-run-notify",
        action="store_true",
        help="Muestra curl de notificacion pero no lo envia.",
    )
    parser.add_argument(
        "--always-notify",
        action="store_true",
        help="Notifica aunque no haya cambios de archivos en la iteracion.",
    )
    parser.add_argument(
        "--exclude-patterns",
        default=os.getenv("TASK_NOTIFY_EXCLUDE_PATTERNS", "").strip(),
        help=(
            "Patrones separados por coma a excluir de la deteccion "
            "(default: TASK_NOTIFY_EXCLUDE_PATTERNS o patrones operativos internos)."
        ),
    )
    parser.add_argument(
        "--debug-change-detection",
        action="store_true",
        help="Imprime diagnostico detallado de deteccion de cambios y decision de notificacion.",
    )
    parser.add_argument(
        "codex_command",
        nargs=argparse.REMAINDER,
        help="Comando de Codex a ejecutar. Ej: -- codex",
    )
    args = parser.parse_args()
    return args


def normalize_codex_command(command_parts: list[str]) -> list[str]:
    if command_parts and command_parts[0] == "--":
        command_parts = command_parts[1:]
    if not command_parts:
        return ["codex"]
    return command_parts


def main() -> int:
    settings = load_settings()
    args = parse_args()

    codex_command = normalize_codex_command(args.codex_command)
    repository_name = args.repository_name.strip() or detect_repository_name(settings.repository_name)
    api_url = args.api_url.strip() or "http://127.0.0.1:8000/tasks/start"
    exclude_patterns = parse_exclude_patterns(args.exclude_patterns)
    if args.duration_seconds < 0:
        print("ERROR: --duration-seconds no puede ser negativo.", file=sys.stderr)
        return 2

    print("[codex-run] Ejecutando Codex CLI:")
    print(" ".join(codex_command))
    snapshot_before, excluded_before = get_working_tree_snapshot(exclude_patterns)
    started_at = time.perf_counter()
    codex_exit_code = 0

    try:
        result = subprocess.run(
            codex_command,
            cwd=PROJECT_ROOT,
            check=False,
        )
        codex_exit_code = result.returncode
    except FileNotFoundError:
        print(f"ERROR: comando no encontrado: {codex_command[0]}", file=sys.stderr)
        codex_exit_code = 127
    except KeyboardInterrupt:
        codex_exit_code = 130

    elapsed_seconds = time.perf_counter() - started_at
    force_fail = codex_exit_code != 0

    snapshot_after, excluded_after = get_working_tree_snapshot(exclude_patterns)
    changed_files_count = 0
    has_file_changes = True
    changed_files: list[str] = []
    if snapshot_before is not None and snapshot_after is not None:
        changed_files = get_changed_files(snapshot_before, snapshot_after)
        changed_files_count = len(changed_files)
        has_file_changes = changed_files_count > 0
    elif snapshot_before is None or snapshot_after is None:
        if args.on_git_error == "skip":
            has_file_changes = False
            print("[codex-run] Advertencia: no se pudo evaluar cambios reales de archivos. Se omite notificacion.")
        else:
            has_file_changes = True
            print("[codex-run] Advertencia: no se pudo evaluar cambios reales de archivos. Se notificara por seguridad.")

    if args.debug_change_detection:
        print(
            f"[codex-run][debug] patrones_excluidos={exclude_patterns} "
            f"excluidos_before={excluded_before} excluidos_after={excluded_after}"
        )
        if snapshot_before is not None and snapshot_after is not None:
            print(
                f"[codex-run][debug] archivos_evaluados_before={len(snapshot_before)} "
                f"archivos_evaluados_after={len(snapshot_after)} cambios={changed_files_count}"
            )
            if changed_files_count:
                preview = ", ".join(changed_files[:20])
                suffix = " ..." if changed_files_count > 20 else ""
                print(f"[codex-run][debug] archivos_con_cambio={preview}{suffix}")
        else:
            print(
                "[codex-run][debug] snapshot_before_o_after=None "
                f"on_git_error={args.on_git_error}"
            )

    if not args.always_notify and not has_file_changes:
        print("[codex-run] No hubo cambios de archivos en la iteracion. Se omite notificacion.")
        if args.debug_change_detection:
            print(
                "[codex-run][debug] razon_omision=no_file_changes "
                f"always_notify={args.always_notify} codex_exit_code={codex_exit_code}"
            )
        return codex_exit_code

    payload = build_payload(
        duration_seconds=args.duration_seconds,
        force_fail=force_fail,
        modified_files_count=changed_files_count,
        repository_name=repository_name,
        execution_time_seconds=elapsed_seconds,
    )

    print(
        "[codex-run] Notificando /tasks/start con "
        f"repo={repository_name} tiempo={elapsed_seconds:.2f}s force_fail={force_fail}"
    )
    if args.dry_run_notify:
        print("[codex-run] dry-run-notify activo: no se enviara notificacion real a Telegram.")
    notify_exit_code = send_task_notification(
        api_url=api_url,
        payload=payload,
        dry_run=args.dry_run_notify,
    )
    if notify_exit_code != 0:
        print(f"ERROR: fallo notificacion curl (exit={notify_exit_code})", file=sys.stderr)
        if codex_exit_code == 0:
            return notify_exit_code
    elif args.dry_run_notify:
        print("[codex-run] Simulacion completada. No hubo envio real.")
    else:
        print("[codex-run] Notificacion enviada correctamente.")

    return codex_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
