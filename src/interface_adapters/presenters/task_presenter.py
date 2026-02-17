from datetime import datetime, timezone

from src.entities.task import StartedTask


def _to_utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def present_task_started(task: StartedTask) -> dict[str, object]:
    return {
        "status": "started",
        "chat_id": task.chat_id,
        "duration_seconds": task.duration_seconds,
        "force_fail": task.force_fail,
        "modified_files_count": task.modified_files_count,
        "repository_name": task.repository_name,
        "execution_time_seconds": task.execution_time_seconds,
        "start_datetime": _to_utc_iso(task.start_datetime),
        "end_datetime": _to_utc_iso(task.end_datetime),
    }
