from datetime import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskExecutionRequest:
    duration_seconds: float
    force_fail: bool = False
    modified_files_count: int = 0
    repository_name: str | None = None
    execution_time_seconds: float | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None


@dataclass(frozen=True)
class StartedTask:
    chat_id: int
    duration_seconds: float
    force_fail: bool
    modified_files_count: int = 0
    repository_name: str | None = None
    execution_time_seconds: float | None = None
    start_datetime: datetime | None = None
    end_datetime: datetime | None = None
