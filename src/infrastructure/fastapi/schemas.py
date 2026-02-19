from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TaskStartRequestModel(BaseModel):
    duration_seconds: float = Field(default=1.0, ge=0.0, le=600.0)
    force_fail: bool = False
    modified_files_count: int = Field(default=0, ge=0, le=200000)
    repository_name: str | None = Field(default=None, max_length=240)
    execution_time_seconds: float | None = Field(default=None, ge=0.0, le=86400.0)
    start_datetime: datetime | None = Field(default=None)
    end_datetime: datetime | None = Field(default=None)


class HealthResponseModel(BaseModel):
    service: str
    status: str


class ContactRequestModel(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(
        min_length=5,
        max_length=254,
        pattern=r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$",
    )
    message: str = Field(min_length=1, max_length=5000)
    meta: dict[str, Any] = Field(default_factory=dict)
    attribution: dict[str, Any] = Field(default_factory=dict)


class AcceptedResponseModel(BaseModel):
    request_id: str
    status: str
    message: str


class ErrorBodyModel(BaseModel):
    code: str
    message: str


class ErrorResponseModel(BaseModel):
    request_id: str
    error: ErrorBodyModel
