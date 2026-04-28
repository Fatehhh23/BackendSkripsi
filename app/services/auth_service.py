from sqlalchemy.orm import Session
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from app.database.models import User
from app.schemas.auth import UserRegister, UserLogin
from app.core.security import verify_password, get_password_hash, create_access_token
from datetime import datetime
import logging
import secrets
import string
import requests
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from app.schemas.auth import UserRegister, UserLogin, SocialLoginRequest

logger = logging.getLogger(__name__)

class AuthService:
    """Service untuk handle authentication"""
    
    @staticmethod
    async def register_user(db: AsyncSession, user_data: UserRegister) -> User:
        """Register user baru"""
        
        # Check email sudah ada?
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Check username sudah ada?
        result = await db.execute(
            select(User).where(User.username == user_data.username)
        )
        existing_username = result.scalar_one_or_none()
        
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        
        # Hash password
        hashed_password = get_password_hash(user_data.password)
        
        # Create user
        new_user = User(
            email=user_data.email,
            username=user_data.username,
            password_hash=hashed_password,
            full_name=user_data.full_name
        )
        
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        
        logger.info(f"✅ New user registered: {new_user.email}")
        return new_user
    
    @staticmethod
    async def login_user(db: AsyncSession, login_data: UserLogin) -> dict:
        """Login user dan return JWT token"""
        
        # Find user by email
        result = await db.execute(
            select(User).where(User.email == login_data.email)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Verify password
        if not verify_password(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is deactivated"
            )
        
        # Update last login
        user.last_login = datetime.utcnow()
        await db.commit()
        
        # Create access token
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email, "role": user.role.value}
        )
        
        logger.info(f"✅ User logged in: {user.email}")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user
        }

    @staticmethod
    async def verify_google_token(token: str) -> dict:
        """Verify Google Access Token"""
        try:
            # Verify via UserInfo endpoint (supports Access Token from custom buttons)
            response = requests.get(
                'https://www.googleapis.com/oauth2/v3/userinfo',
                params={'access_token': token}
            )
            
            if response.status_code != 200:
                # Fallback: Try ID Token verification if access token fails
                try:
                    id_info = id_token.verify_oauth2_token(token, google_requests.Request())
                    return {
                        "email": id_info['email'],
                        "full_name": id_info.get('name'),
                        "picture": id_info.get('picture')
                    }
                except ValueError:
                    raise ValueError("Failed to verify token with Google")
                
            data = response.json()
            return {
                "email": data['email'],
                "full_name": data.get('name'),
                "picture": data.get('picture')
            }
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid Google token: {str(e)}"
            )



    @staticmethod
    async def social_login(db: AsyncSession, login_data: SocialLoginRequest) -> dict:
        """Handle social login (Google/Facebook/Apple)"""
        
        user_info = None
        
        # 1. Verify Token
        # 1. Verify Token
        if login_data.provider.lower() == 'google':
            user_info = await AuthService.verify_google_token(login_data.token)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported provider calls: {login_data.provider}"
            )
            
        email = user_info['email']
        
        # 2. Check if user exists
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if not user:
            # 3. Create new user if not exists
            # Generate random secure password (since they login via social)
            alphabet = string.ascii_letters + string.digits
            random_password = ''.join(secrets.choice(alphabet) for i in range(20))
            hashed_password = get_password_hash(random_password)
            
            # Use email prefix as username if possible, check uniqueness logic later
            base_username = email.split('@')[0]
            # Ensure username is unique - simple retry logic or append random
            username = base_username
            
            # Check username uniqueness
            username_exists = await db.execute(select(User).where(User.username == username))
            if username_exists.scalar_one_or_none():
                username = f"{base_username}_{secrets.token_hex(2)}"
            
            new_user = User(
                email=email,
                username=username,
                password_hash=hashed_password,
                full_name=user_info.get('full_name', ''),
                is_active=True,
                is_verified=True # Social login emails are usually verified
            )
            
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)
            user = new_user
            logger.info(f"✅ New user registered via {login_data.provider}: {user.email}")
            
        else:
             logger.info(f"✅ User logged in via {login_data.provider}: {user.email}")
        
        # 4. Generate Token
        access_token = create_access_token(
            data={"sub": str(user.id), "email": user.email, "role": user.role.value}
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": user
        }
    
    @staticmethod
    async def get_current_user(db: AsyncSession, user_id: str) -> User:
        """Get current user by ID"""
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user
