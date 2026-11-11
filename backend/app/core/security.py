import hashlib
from hmac import compare_digest
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union
import jwt
import bcrypt
from backend.app.core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    password = plain_password.encode()
    if hashed_password.startswith("$2"):
        if len(password) > 72:
            return False
        try:
            return bcrypt.checkpw(password, hashed_password.encode())
        except ValueError:
            return False
    # Existing databases can contain hashes written by the previous fallback.
    return compare_digest(hashlib.sha256(password).hexdigest().encode("ascii"), hashed_password.encode())


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def create_access_token(subject: Union[str, Any], school_id: Optional[str] = None, role: Optional[str] = None, expires_delta: Optional[timedelta] = None, *, demo_root: bool = False) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode: Dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access"
    }
    if school_id:
        to_encode["school_id"] = school_id
    if role:
        to_encode["role"] = role
    if demo_root:
        to_encode["demo_root"] = True
        
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode: Dict[str, Any] = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "refresh"
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

