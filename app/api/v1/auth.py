from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.connection import get_db
from app.schemas.auth import UserRegister, UserLogin, TokenResponse, UserResponse, UserProfile, SocialLoginRequest
from app.services.auth_service import AuthService
from app.core.dependencies import get_current_user
from app.database.models import User

router = APIRouter()

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """
    Register user baru.
    
    - **email**: Email valid (akan digunakan untuk login)
    - **username**: Username unique (3-50 karakter)
    - **password**: Password minimal 6 karakter
    - **full_name**: Nama lengkap (optional)
    
    Returns: User object yang baru dibuat
    """
    user = await AuthService.register_user(db, user_data)
    return user

@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: UserLogin,
    db: Session = Depends(get_db)
):
    """
    Login user dan return JWT access token.
    
    - **email**: Email terdaftar
    - **password**: Password yang benar
    
    Returns JWT token yang harus digunakan di header:
    ```
    Authorization: Bearer <token>
    ```
    
    Token valid selama 24 jam.
    """
    result = await AuthService.login_user(db, login_data)
    return result

@router.post("/social-login", response_model=TokenResponse)
async def social_login(
    login_data: SocialLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login/Register using Social Media (Google, Facebook, Apple).
    """
    result = await AuthService.social_login(db, login_data)
    return result

@router.get("/me", response_model=UserProfile)
async def get_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get current user profile.
    
    **Requires authentication** - Harus login dulu!
    
    Returns profile user yang sedang login.
    """
    return current_user

@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_user)
):
    """
    Logout user.
    
    Note: JWT bersifat stateless, jadi logout dilakukan di frontend 
    dengan menghapus token dari localStorage.
    
    Endpoint ini hanya untuk logging purposes.
    """
    return {
        "message": "Successfully logged out",
        "detail": "Please remove the token from your client storage"
    }
