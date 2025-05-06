import uuid
from sqlmodel import Field, Relationship, SQLModel


class Event(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    token: str = Field(default_factory=lambda: str(uuid.uuid4())[:8], unique=True, index=True)
    scans: list["Scan"] = Relationship(back_populates="event")


class Scan(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # Change from hacker_id to uid to match your Account_User model
    hacker_id: uuid.UUID = Field(foreign_key="account_user.uid", index=True)
    event_id: uuid.UUID = Field(foreign_key="event.id", index=True)
    
    event: Event = Relationship(back_populates="scans")