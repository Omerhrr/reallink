"""
Authentication Routes for RealLink Ecosystem
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
import os

from app.models import User, UserRole
from app.dependencies import get_db
from app.utils import hash_user_address

router = APIRouter()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = os.getenv("SECRET_KEY", "reallink_secret_key_change_in_production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24


# Pydantic models
class UserCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = "OWNER"
    password: str


class UserLogin(BaseModel):
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    password: str


class UserResponse(BaseModel):
    id: int
    address: str
    name: str
    phone: Optional[str]
    email: Optional[str]
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


def create_access_token(data: dict, expires_delta: timedelta = None):
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return user


@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Check if user already exists
    identifier = user_data.phone or user_data.email
    if not identifier:
        raise HTTPException(status_code=400, detail="Phone or email is required")

    # Check existing
    existing = db.query(User).filter(
        (User.phone == user_data.phone) | (User.email == user_data.email)
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    # Create user
    hashed_address = hash_user_address(identifier)
    hashed_password = hash_password(user_data.password)

    try:
        role = UserRole(user_data.role.upper()) if user_data.role else UserRole.OWNER
    except ValueError:
        role = UserRole.OWNER

    user = User(
        address=hashed_address,
        name=user_data.name,
        phone=user_data.phone,
        email=user_data.email,
        password_hash=hashed_password,
        role=role
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Create access token
    access_token = create_access_token({"user_id": user.id})

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            address=user.address,
            name=user.name,
            phone=user.phone,
            email=user.email,
            role=user.role.value,
            created_at=user.created_at
        )
    )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Login user"""
    identifier = credentials.phone or credentials.email
    if not identifier:
        raise HTTPException(status_code=400, detail="Phone or email is required")

    user = db.query(User).filter(
        (User.phone == credentials.phone) | (User.email == credentials.email)
    ).first()

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Verify password
    if not user.password_hash or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check if user is active
    if not user.is_active:
        raise HTTPException(status_code=401, detail="Account is deactivated")

    access_token = create_access_token({"user_id": user.id})

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            address=user.address,
            name=user.name,
            phone=user.phone,
            email=user.email,
            role=user.role.value,
            created_at=user.created_at
        )
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return UserResponse(
        id=current_user.id,
        address=current_user.address,
        name=current_user.name,
        phone=current_user.phone,
        email=current_user.email,
        role=current_user.role.value,
        created_at=current_user.created_at
    )


@router.put("/me", response_model=UserResponse)
async def update_me(
    name: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user profile"""
    if name:
        current_user.name = name
    if phone:
        current_user.phone = phone
    if email:
        current_user.email = email

    db.commit()
    db.refresh(current_user)

    return UserResponse(
        id=current_user.id,
        address=current_user.address,
        name=current_user.name,
        phone=current_user.phone,
        email=current_user.email,
        role=current_user.role.value,
        created_at=current_user.created_at
    )
