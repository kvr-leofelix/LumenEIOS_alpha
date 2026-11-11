from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_user, require_roles, require_school_access, user_school_ids
from backend.app.db.session import get_db
from backend.app.models.entities import School, ClassSection, User, AuditEvent, utc_now
from backend.app.schemas.schools import SchoolOut, SchoolCreate, SchoolUpdate, ClassSectionOut

router = APIRouter(prefix="/schools", tags=["Schools"])


@router.get("", response_model=List[SchoolOut])
async def list_schools(
    tier: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(School).filter(School.is_archived == False)
    if current_user.role != "admin":
        query = query.filter(School.id.in_(await user_school_ids(db, current_user)))
    if tier and tier != "all":
        query = query.filter(School.infrastructure_tier == tier)
    if search:
        query = query.filter(School.name.ilike(f"%{search}%") | School.location.ilike(f"%{search}%"))

    result = await db.execute(query.order_by(School.name))
    return result.scalars().all()


@router.post("", response_model=SchoolOut, status_code=status.HTTP_201_CREATED)
async def create_school(
    req: SchoolCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    school = School(**req.model_dump())
    db.add(school)
    
    audit = AuditEvent(
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
        user_id=admin.id,
        user_name=admin.name,
        action="Onboarded New School",
        details=f"Onboarded campus: {school.name} ({school.infrastructure_tier})",
        category="system"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(school)
    return school


@router.get("/{school_id}", response_model=SchoolOut)
async def get_school(school_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    await require_school_access(db, current_user, school_id)
    result = await db.execute(select(School).filter(School.id == school_id))
    school = result.scalars().first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")
    return school


@router.patch("/{school_id}", response_model=SchoolOut)
async def update_school(
    school_id: str,
    req: SchoolUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles("admin", "principal"))
):
    result = await db.execute(select(School).filter(School.id == school_id))
    school = result.scalars().first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")

    for field, val in req.model_dump(exclude_unset=True).items():
        setattr(school, field, val)

    await db.commit()
    await db.refresh(school)
    return school


@router.post("/{school_id}/archive")
async def archive_school(
    school_id: str,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles("admin"))
):
    result = await db.execute(select(School).filter(School.id == school_id))
    school = result.scalars().first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")
    school.is_archived = True
    await db.commit()
    return {"message": f"School {school.name} archived."}


@router.get("/{school_id}/classes", response_model=List[ClassSectionOut])
async def list_school_classes(
    school_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await require_school_access(db, current_user, school_id)
    result = await db.execute(select(ClassSection).filter(ClassSection.school_id == school_id))
    return result.scalars().all()

