from src.entities.task import StartedTask


def present_task_started(task: StartedTask) -> dict[str, object]:
    return {
        "status": "started",
        "chat_id": task.chat_id,
        "duration_seconds": task.duration_seconds,
        "force_fail": task.force_fail,
        "commit_proposal": task.commit_proposal,
        "repository_name": task.repository_name,
        "execution_time_seconds": task.execution_time_seconds,
    }
