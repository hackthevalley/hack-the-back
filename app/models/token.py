from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: str | None = None
    fullName: str | None = None
    firstName: str | None = None
    lastName: str | None = None
    scopes: list[str] = []
