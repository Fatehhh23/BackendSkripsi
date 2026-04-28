from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

# ============================================
# Request Schemas
# ============================================

class UserRegister(BaseModel):
    """Schema untuk registrasi user baru"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    full_name: Optional[str] = None

class UserLogin(BaseModel):
    """Schema untuk login"""
    email: EmailStr
    password: str

class SocialLoginRequest(BaseModel):
    """Schema untuk login via social media"""
    provider: str
    token: str

# ============================================
# Response Schemas
# ============================================

class UserResponse(BaseModel):
    """Schema untuk response user data"""
    id: UUID
    email: str
    username: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

class UserProfile(UserResponse):
    """Schema untuk user profile dengan info lengkap"""
    last_login: Optional[datetime]
    is_verified: bool

class TokenResponse(BaseModel):
    """Schema untuk response token"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

