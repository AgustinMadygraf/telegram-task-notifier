from pydantic import BaseModel, Field


class TaskStartRequestModel(BaseModel):
    duration_seconds: float = Field(default=1.0, ge=0.0, le=600.0)
    force_fail: bool = False
    commit_proposal: str | None = Field(default=None, max_length=240)
