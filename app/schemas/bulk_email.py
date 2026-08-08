from pydantic import BaseModel, Field

from app.models.forms import StatusEnum


class BulkEmailRequest(BaseModel):
    template_path: str
    status: StatusEnum
    subject: str
    text_body: str
    context: dict = Field(default_factory=dict)
