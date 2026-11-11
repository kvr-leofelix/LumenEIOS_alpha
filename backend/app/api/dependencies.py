from typing import List, Optional
from fastapi import Depends, HTTPException, Header, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

from backend.app.core.config import settings
from backend.app.core.security import decode_token
from backend.app.db.session import get_db
from backend.app.models.entities import User, SchoolMembership

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    if not token:
        # Fallback in demo mode if requested without token: return admin user
        if settings.DEMO_MODE:
            result = await db.execute(select(User).filter(User.role == "admin").limit(1))
            admin = result.scalars().first()
            if admin:
                return admin
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        if (
            not user_id or payload.get("type") != "access"
            or (payload.get("demo_root") and not settings.demo_root_enabled)
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials.")

    result = await db.execute(select(User).filter(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    return user


def require_roles(*allowed_roles: str, authenticated: bool = False):
    def role_checker(
        current_user: User = Depends(get_current_user),
        token: Optional[str] = Depends(oauth2_scheme),
    ) -> User:
        if authenticated and not token:
            raise HTTPException(status_code=401, detail="Authentication token required.")
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role '{current_user.role}'. Required: {allowed_roles}."
            )
        return current_user
    return role_checker


async def user_school_ids(db: AsyncSession, user: User) -> set[str]:
    """Schools a non-admin user belongs to: their home school plus active memberships."""
    rows = await db.execute(
        select(SchoolMembership.school_id).where(
            SchoolMembership.user_id == user.id, SchoolMembership.is_active == True  # noqa: E712
        )
    )
    return {school_id for school_id in rows.scalars()} | ({user.school_id} if user.school_id else set())


async def require_school_access(db: AsyncSession, user: User, school_id: str) -> None:
    """Admins reach every school; everyone else only the schools they belong to."""
    if user.role == "admin" or school_id in await user_school_ids(db, user):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You don't have access to this school.")


async def get_current_school_context(
    x_school_id: Optional[str] = Header(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> str:
    """
    Resolves the active school context.
    Admins can select any school via X-School-Id.
    Other roles are restricted to their authorized school.
    """
    target = x_school_id or current_user.school_id or "school-1"
    
    if current_user.role == "admin":
        return target
        
    if current_user.school_id == target:
        return target
        
    # Check memberships
    result = await db.execute(
        select(SchoolMembership).filter(
            SchoolMembership.user_id == current_user.id,
            SchoolMembership.school_id == target,
            SchoolMembership.is_active == True
        )
    )
    if result.scalars().first():
        return target

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Unauthorized school context access."
    )

