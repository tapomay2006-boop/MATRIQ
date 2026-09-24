import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserCreate(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    full_name: str | None = None
    password: str = Field(min_length=6, max_length=128)
    role: str | None = "cpse_admin"


class UserLogin(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    password: str


class UserOAuth(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    name: str | None = None
    image: str | None = None
    role: str | None = "cpse_admin"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str | None = None
    role: str = "cpse_admin"
    is_active: bool = True
    created_at: datetime
