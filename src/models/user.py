from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    is_verified: bool = False


class UserResponse(UserBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AuthStateResponse(BaseModel):
    authenticated: bool
    message: str
    user: Optional[UserResponse] = None


class MessageResponse(BaseModel):
    success: bool = True
    message: str
