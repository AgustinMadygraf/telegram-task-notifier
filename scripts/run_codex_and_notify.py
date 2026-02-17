import argparse
from datetime import datetime, timezone
import fnmatch
import hashlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from notify_common import build_payload, detect_repository_name, send_task_notification
from src.shared.config import load_settings

DEFAULT_OPERATIONAL_EXCLUDE_PATTERNS = (
    "*.log",
    "*.tmp",
    "*.temp",
    ".last_chat_id",
    ".last_chat_id.tmp",
)
MIN_REPORTED_EXECUTION_SECONDS = 0.01


def iso_utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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
        description=(
            "Ejecuta Codex CLI y notifica /tasks/start por iteracion cuando "
            "haya cambios de archivos y la actividad quede estable."
        ),
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
        help="Reservado para compatibilidad. No aplica en modo por iteracion.",
    )
    parser.add_argument(
        "--idle-seconds",
        type=float,
        default=float(os.getenv("TASK_NOTIFY_IDLE_SECONDS", "2.5")),
        help="Segundos sin cambios para considerar cierre de iteracion (default: 2.5).",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=float(os.getenv("TASK_NOTIFY_POLL_INTERVAL_SECONDS", "0.75")),
        help="Frecuencia de polling de cambios de archivos (default: 0.75).",
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
    return command_parts


def resolve_codex_command(command_parts: list[str]) -> list[str]:
    if command_parts:
        return command_parts
    if shutil.which("codex") or shutil.which("codex.cmd") or shutil.which("codex.exe"):
        return ["codex"]
    if shutil.which("npx") or shutil.which("npx.cmd") or shutil.which("npx.exe"):
        return ["npx", "@openai/codex"]
    return []


def resolve_windows_command(binary: str) -> str | None:
    """Resolve command path across common Windows executable extensions."""
    return shutil.which(binary) or shutil.which(f"{binary}.cmd") or shutil.which(f"{binary}.exe")


def main() -> int:
    settings = load_settings()
    args = parse_args()

    normalized_command = normalize_codex_command(args.codex_command)
    codex_command = resolve_codex_command(normalized_command)
    repository_name = args.repository_name.strip() or detect_repository_name(settings.repository_name)
    api_url = args.api_url.strip() or "http://127.0.0.1:8000/tasks/start"
    exclude_patterns = parse_exclude_patterns(args.exclude_patterns)
    if args.duration_seconds < 0:
        print("ERROR: --duration-seconds no puede ser negativo.", file=sys.stderr)
        return 2
    if args.idle_seconds <= 0:
        print("ERROR: --idle-seconds debe ser mayor a 0.", file=sys.stderr)
        return 2
    if args.poll_interval_seconds <= 0:
        print("ERROR: --poll-interval-seconds debe ser mayor a 0.", file=sys.stderr)
        return 2

    print("[codex-run] Ejecutando Codex CLI:")
    if not normalized_command and codex_command[:2] == ["npx", "@openai/codex"]:
        print("[codex-run] Aviso: 'codex' no encontrado en PATH. Se usa fallback: npx @openai/codex")
    if not codex_command:
        print(
            "ERROR: no se encontro 'codex' ni 'npx' en PATH. "
            "Instala Codex CLI o Node.js (npx) o pasa el comando explicito con '-- <comando>'.",
            file=sys.stderr,
        )
        return 127
    print(" ".join(codex_command))
    if args.always_notify:
        print("[codex-run] Aviso: --always-notify no aplica en modo por iteracion y sera ignorado.")

    baseline_snapshot, baseline_excluded = get_working_tree_snapshot(exclude_patterns)
    if baseline_snapshot is None:
        if args.on_git_error == "skip":
            print("[codex-run] Advertencia: no se pudo iniciar deteccion git. Se omiten notificaciones.")
        else:
            print("[codex-run] Advertencia: no se pudo iniciar deteccion git. Se intentara continuar.", file=sys.stderr)

    started_at = time.perf_counter()
    started_at_iso = iso_utc_now()
    codex_exit_code = 0

    process = None
    codex_in_path = resolve_windows_command("codex")
    npx_in_path = resolve_windows_command("npx")

    primary_command = codex_command
    command_head = codex_command[0].lower() if codex_command else ""
    trailing_args = codex_command[1:] if len(codex_command) > 1 else []
    if command_head == "codex" and codex_in_path:
        primary_command = [codex_in_path, *trailing_args]
    elif command_head == "npx" and npx_in_path:
        primary_command = [npx_in_path, *trailing_args]

    launch_attempts: list[list[str]] = [primary_command]
    if command_head == "codex" and npx_in_path:
        launch_attempts.append([npx_in_path, "@openai/codex", *trailing_args])

    for candidate_cmd in launch_attempts:
        if not candidate_cmd:
            continue
        try:
            process = subprocess.Popen(
                candidate_cmd,
                cwd=PROJECT_ROOT,
            )
            if len(candidate_cmd) >= 2 and candidate_cmd[1] == "@openai/codex":
                codex_command = candidate_cmd
                print("[codex-run] Aviso: fallback de ejecucion aplicado: npx @openai/codex")
            break
        except FileNotFoundError:
            continue

    if process is None:
        print(
            "ERROR: no se pudo iniciar Codex CLI. "
            f"codex_en_path={bool(codex_in_path)} npx_en_path={bool(npx_in_path)}. "
            "Prueba con '-- npx @openai/codex' o instala Codex CLI.",
            file=sys.stderr,
        )
        return 127

    if args.debug_change_detection:
        print(
            "[codex-run][debug] modo_notificacion=por_iteracion "
            f"idle_seconds={args.idle_seconds} poll_interval={args.poll_interval_seconds}"
        )
        print(
            f"[codex-run][debug] patrones_excluidos={exclude_patterns} excluidos_baseline={baseline_excluded}"
        )
        if baseline_snapshot is not None:
            print(f"[codex-run][debug] archivos_evaluados_baseline={len(baseline_snapshot)}")

    last_seen_snapshot = baseline_snapshot
    last_change_ts = time.perf_counter()
    notified_turns = 0

    try:
        while True:
            process_code = process.poll()
            if process_code is not None:
                codex_exit_code = process_code
                break

            current_snapshot, excluded_current = get_working_tree_snapshot(exclude_patterns)
            now = time.perf_counter()

            if baseline_snapshot is None or current_snapshot is None:
                if args.on_git_error == "skip":
                    if args.debug_change_detection:
                        print("[codex-run][debug] git_error_con_skip=true (sin notificacion en esta muestra)")
                    time.sleep(args.poll_interval_seconds)
                    continue
                print(
                    "[codex-run] Advertencia: error leyendo git en modo por iteracion. "
                    "No se pudo evaluar la muestra actual.",
                    file=sys.stderr,
                )
                time.sleep(args.poll_interval_seconds)
                continue

            if last_seen_snapshot is None or current_snapshot != last_seen_snapshot:
                last_change_ts = now
                last_seen_snapshot = current_snapshot
                if args.debug_change_detection:
                    print(
                        f"[codex-run][debug] cambio_detectado archivos_evaluados={len(current_snapshot)} "
                        f"excluidos_actual={excluded_current}"
                    )

            changed_files = get_changed_files(baseline_snapshot, current_snapshot)
            changed_files_count = len(changed_files)
            idle_elapsed = now - last_change_ts
            is_iteration_stable = changed_files_count > 0 and idle_elapsed >= args.idle_seconds

            if args.debug_change_detection:
                print(
                    f"[codex-run][debug] cambios_vs_baseline={changed_files_count} "
                    f"idle_elapsed={idle_elapsed:.2f}s estable={is_iteration_stable}"
                )

            if is_iteration_stable:
                elapsed_seconds = max(now - started_at, MIN_REPORTED_EXECUTION_SECONDS)
                end_datetime_iso = iso_utc_now()
                payload = build_payload(
                    duration_seconds=args.duration_seconds,
                    force_fail=False,
                    modified_files_count=changed_files_count,
                    repository_name=repository_name,
                    execution_time_seconds=elapsed_seconds,
                    start_datetime=started_at_iso,
                    end_datetime=end_datetime_iso,
                )
                print(
                    "[codex-run] Iteracion estable detectada. "
                    f"Notificando cambios={changed_files_count} repo={repository_name} tiempo={elapsed_seconds:.2f}s"
                )
                if args.debug_change_detection and changed_files_count:
                    preview = ", ".join(changed_files[:20])
                    suffix = " ..." if changed_files_count > 20 else ""
                    print(f"[codex-run][debug] archivos_notificados={preview}{suffix}")

                notify_exit_code = send_task_notification(
                    api_url=api_url,
                    payload=payload,
                    dry_run=args.dry_run_notify,
                )
                if notify_exit_code != 0:
                    print(f"ERROR: fallo notificacion curl (exit={notify_exit_code})", file=sys.stderr)
                elif args.dry_run_notify:
                    print("[codex-run] Simulacion completada. No hubo envio real.")
                else:
                    print("[codex-run] Notificacion enviada correctamente.")

                baseline_snapshot = current_snapshot
                last_seen_snapshot = current_snapshot
                last_change_ts = now
                notified_turns += 1

            time.sleep(args.poll_interval_seconds)
    except KeyboardInterrupt:
        try:
            process.terminate()
        except OSError:
            pass
        codex_exit_code = 130

    if args.debug_change_detection:
        print(f"[codex-run][debug] proceso_codex_finalizado exit={codex_exit_code} turnos_notificados={notified_turns}")

    return codex_exit_code


if __name__ == "__main__":
    raise SystemExit(main())
