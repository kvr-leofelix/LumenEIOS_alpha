from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import require_roles, require_school_access
from backend.app.core.security import get_password_hash
from backend.app.db.session import get_db
from backend.app.models.entities import AuditEvent, School, User, utc_now
from backend.app.schemas.auth import UserOut
from backend.app.schemas.teachers import TeacherCreate

router = APIRouter(prefix="/teachers", tags=["Teachers"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_teacher(
    body: TeacherCreate,
    db: AsyncSession = Depends(get_db),
    principal: User = Depends(require_roles("principal")),
):
    name = body.name.strip()
    email = body.email.lower()
    if not name:
        raise HTTPException(status_code=400, detail="Enter the teacher's name.")

    school = (await db.execute(select(School).filter(School.id == body.school_id))).scalars().first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")
    await require_school_access(db, principal, body.school_id)

    existing = (await db.execute(select(User).filter(User.email == email))).scalars().first()
    if existing:
        raise HTTPException(status_code=400, detail="A user with this email already exists.")

    teacher = User(
        email=email,
        name=name,
        hashed_password=get_password_hash("demo123"),
        role="teacher",
        school_id=body.school_id,
        designation=body.designation.strip() or "Teacher",
    )
    db.add(teacher)
    db.add(
        AuditEvent(
            timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
            user_id=principal.id,
            user_name=principal.name,
            action="Teacher Added",
            details=f"Added teacher {name} ({email}).",
            category="user",
        )
    )
    await db.commit()
    await db.refresh(teacher)
    return teacher
