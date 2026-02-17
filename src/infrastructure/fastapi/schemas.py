from datetime import datetime

from pydantic import BaseModel, Field


class TaskStartRequestModel(BaseModel):
    duration_seconds: float = Field(default=1.0, ge=0.0, le=600.0)
    force_fail: bool = False
    modified_files_count: int = Field(default=0, ge=0, le=200000)
    repository_name: str | None = Field(default=None, max_length=240)
    execution_time_seconds: float | None = Field(default=None, ge=0.0, le=86400.0)
    start_datetime: datetime | None = Field(default=None)
    end_datetime: datetime | None = Field(default=None)
