from pydantic import BaseModel


class UIDRequest(BaseModel):
    uid: str
