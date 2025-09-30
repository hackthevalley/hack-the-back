from typing import Optional

from pydantic import BaseModel

from app.models.forms import (
    StatusEnum,
)


class UIDRequest(BaseModel):
    uid: str


class BulkEmailRequest(BaseModel):
    template_path: str
    status: StatusEnum
    subject: str
    text_body: str
    context: Optional[dict] = {}
