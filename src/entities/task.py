from dataclasses import dataclass


@dataclass(frozen=True)
class TaskExecutionRequest:
    duration_seconds: float
    force_fail: bool = False
    commit_proposal: str | None = None
    repository_name: str | None = None
    execution_time_seconds: float | None = None


@dataclass(frozen=True)
class StartedTask:
    chat_id: int
    duration_seconds: float
    force_fail: bool
    commit_proposal: str | None = None
    repository_name: str | None = None
    execution_time_seconds: float | None = None
