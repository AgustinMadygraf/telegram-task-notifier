from pydantic import BaseModel, Field


class TaskStartRequestModel(BaseModel):
    duration_seconds: float = Field(default=1.0, ge=0.0, le=600.0)
    force_fail: bool = False
    commit_proposal: str | None = Field(default=None, max_length=240)
    repository_name: str | None = Field(default=None, max_length=240)
    execution_time_seconds: float | None = Field(default=None, ge=0.0, le=86400.0)
