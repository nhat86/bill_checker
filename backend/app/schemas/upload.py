import uuid

from pydantic import BaseModel


class UploadResult(BaseModel):
    object_key: str
    kind: str
    session_id: uuid.UUID
    size_bytes: int
    content_type: str | None
