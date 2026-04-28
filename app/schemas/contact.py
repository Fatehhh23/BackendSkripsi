from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime
from typing import Optional

class ContactMessageCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Full name of the sender")
    email: EmailStr = Field(..., description="Email address of the sender")
    subject: str = Field(..., min_length=2, max_length=255, description="Subject of the message")
    message: str = Field(..., min_length=10, description="Content of the message")

class ContactMessageResponse(BaseModel):
    id: UUID
    name: str
    email: EmailStr
    subject: str
    message: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class ContactMessageUpdate(BaseModel):
    status: str = Field(..., description="New status ('unread' or 'resolved')")
