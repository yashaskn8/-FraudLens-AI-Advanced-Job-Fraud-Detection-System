"""
Auth Router — handles user registration and login.
"""
import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from jose import jwt
from passlib.context import CryptContext
from backend.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# In-memory user store (for development — swap with DB in production)
_users_db = {}

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest):
    """Register a new user account."""
    if request.email in _users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    user_id = str(uuid.uuid4())
    hashed_password = pwd_context.hash(request.password)

    _users_db[request.email] = {
        "user_id": user_id,
        "email": request.email,
        "name": request.name or "",
        "hashed_password": hashed_password,
        "created_at": datetime.utcnow().isoformat(),
    }

    token = create_access_token({"sub": user_id, "email": request.email})
    return TokenResponse(
        access_token=token,
        user_id=user_id,
        email=request.email,
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    """Login with email and password."""
    user = _users_db.get(request.email)
    if not user or not pwd_context.verify(request.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token({"sub": user["user_id"], "email": user["email"]})
    return TokenResponse(
        access_token=token,
        user_id=user["user_id"],
        email=user["email"],
    )
