from hmac import compare_digest
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import verify_password, create_access_token, create_refresh_token, decode_token
from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.entities import User, SchoolMembership, AuditEvent, utc_now
from backend.app.seed.seed_data import ROOT_PERSONA_EMAILS
from backend.app.schemas.auth import LoginRequest, TokenResponse, UserOut, SwitchSchoolRequest
from backend.app.api.dependencies import get_current_user, oauth2_scheme

router = APIRouter(prefix="/auth", tags=["Authentication"])


class DemoRoleRequest(BaseModel):
    role: Literal["developer", "admin", "principal", "teacher", "student", "parent"]


def session_response(user: User, *, demo_root: bool = False, role: str | None = None) -> TokenResponse:
    presented_role = role or user.role
    return TokenResponse(
        access_token=create_access_token(user.id, user.school_id, presented_role, demo_root=demo_root),
        refresh_token=create_refresh_token(user.id),
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserOut.model_validate(user).model_copy(update={"demo_root": demo_root, "role": presented_role}),
    )


def developer_role_from_token(token: str | None) -> str | None:
    if not token:
        return None
    payload = decode_token(token)
    if payload.get("demo_root") and payload.get("role") == "developer":
        return "developer"
    return None


ROOT_LOGIN_IDS = {"leofelix", "leofelix@lumeneios.demo"}


async def demo_persona(db: AsyncSession, role: str) -> User:
    # Roster accounts first; the <role>@lumeneios.demo accounts exist only in the test dataset.
    for email in (ROOT_PERSONA_EMAILS.get(role), f"{role}@lumeneios.demo"):
        user = email and await db.scalar(select(User).where(User.email == email, User.role == role))
        if user:
            return user
    user = None
    if not user:
        raise HTTPException(status_code=404, detail="The requested demo persona is missing.")
    return user


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    login_id = req.email.strip().lower()
    demo_root = login_id in ROOT_LOGIN_IDS
    if demo_root and settings.demo_root_enabled and settings.DEMO_ROOT_PASSWORD and compare_digest(
        req.password.encode(), settings.DEMO_ROOT_PASSWORD.get_secret_value().encode()
    ):
        user = await demo_persona(db, "admin")
    elif not demo_root:
        user = await db.scalar(select(User).where(User.email == login_id))
        if user and not verify_password(req.password, user.hashed_password):
            user = None
    else:
        user = None

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    # Log audit event
    audit = AuditEvent(
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
        user_id=user.id,
        user_name=user.name,
        action="User Login",
        details=f"Successful authentication for persona: {'developer' if demo_root else user.role} ({'LEOFELIX' if demo_root else user.email})",
        category="user"
    )
    db.add(audit)
    await db.commit()

    return session_response(user, demo_root=demo_root, role="developer" if demo_root else None)


@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user), token: str | None = Depends(oauth2_scheme)):
    demo_root = bool(token and decode_token(token).get("demo_root"))
    updates: dict = {"demo_root": demo_root}
    if developer_role := developer_role_from_token(token):
        updates["role"] = developer_role
    return UserOut.model_validate(current_user).model_copy(update=updates)


@router.post("/demo-root/role", response_model=TokenResponse)
async def switch_demo_role(
    req: DemoRoleRequest,
    token: str | None = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not token or not decode_token(token).get("demo_root"):
        raise HTTPException(status_code=403, detail="A demo root session is required.")
    if req.role == "developer":
        return session_response(await demo_persona(db, "admin"), demo_root=True, role="developer")
    return session_response(await demo_persona(db, req.role), demo_root=True)


@router.get("/memberships")
async def get_my_memberships(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SchoolMembership).filter(SchoolMembership.user_id == current_user.id))
    memberships = result.scalars().all()
    return [{"id": m.id, "school_id": m.school_id, "role": m.role} for m in memberships]


@router.post("/switch-school", response_model=TokenResponse)
async def switch_school(req: SwitchSchoolRequest, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db), token: str | None = Depends(oauth2_scheme)):
    if current_user.role != "admin":
        result = await db.execute(
            select(SchoolMembership).filter(
                SchoolMembership.user_id == current_user.id,
                SchoolMembership.school_id == req.school_id,
                SchoolMembership.is_active == True
            )
        )
        if not result.scalars().first() and current_user.school_id != req.school_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized school switch.")

    current_user.school_id = req.school_id
    await db.commit()
    await db.refresh(current_user)

    return session_response(
        current_user,
        demo_root=bool(token and decode_token(token).get("demo_root")),
        role=developer_role_from_token(token),
    )


@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    return {"message": "Successfully logged out."}

