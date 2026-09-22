import uuid

from pydantic import BaseModel, Field


class BatchRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=10)


class BatchResultItem(BaseModel):
    url: str
    result: str  # "accepted" | "duplicate" | "invalid"
    job_id: uuid.UUID | None = None
    reason: str | None = None
