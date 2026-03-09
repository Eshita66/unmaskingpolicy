import datetime
from typing import Optional

from sqlmodel import SQLModel, Field

class UserBase(SQLModel):
    name: str
    email: str = Field(unique=True)

class UserCreate(UserBase):
    password: str

class User(UserBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    disabled: bool
    email_verified: bool
    hashed_password: str
    salt: str
    creation_date: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

class UserReadShort(UserBase):
    id: int

class UserRead(UserReadShort):
    creation_date: datetime.datetime