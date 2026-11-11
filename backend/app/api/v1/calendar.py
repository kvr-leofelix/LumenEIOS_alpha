from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_user, require_roles
from backend.app.db.session import get_db
from backend.app.models.entities import School, InstructionalDisruption, CurriculumDay, User, AuditEvent, utc_now
from backend.app.schemas.calendar import DisruptionCreate, DisruptionOut, CalendarAvailabilityOut
from backend.app.services.time_aware_engine import calculate_pacing_metrics

router = APIRouter(tags=["Academic Calendar"])


@router.get("/schools/{school_id}/calendar")
async def get_school_calendar(school_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    school_res = await db.execute(select(School).filter(School.id == school_id))
    school = school_res.scalars().first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")

    disruptions_res = await db.execute(select(InstructionalDisruption).filter(InstructionalDisruption.school_id == school_id))
    disruptions = disruptions_res.scalars().all()

    return {
        "school_id": school.id,
        "school_name": school.name,
        "academic_year": school.academic_year,
        "official_working_days": school.official_working_days,
        "disruptions": [DisruptionOut.model_validate(d) for d in disruptions]
    }


@router.post("/schools/{school_id}/disruptions", response_model=DisruptionOut, status_code=status.HTTP_201_CREATED)
async def record_disruption(
    school_id: str,
    req: DisruptionCreate,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher"))
):
    school_res = await db.execute(select(School).filter(School.id == school_id))
    school = school_res.scalars().first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")

    disruption = InstructionalDisruption(
        school_id=school_id,
        date=req.date,
        reason=req.reason,
        days_lost=req.days_lost,
        recorded_by=educator.name,
        notes=req.notes
    )
    db.add(disruption)

    audit = AuditEvent(
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
        user_id=educator.id,
        user_name=educator.name,
        action="Recorded Lost Instructional Days",
        details=f"Deducted {req.days_lost} teaching days for reason: {req.reason}",
        category="curriculum"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(disruption)
    return disruption


@router.delete("/disruptions/{disruption_id}")
async def delete_disruption(
    disruption_id: str,
    db: AsyncSession = Depends(get_db),
    educator: User = Depends(require_roles("admin", "principal", "teacher"))
):
    res = await db.execute(select(InstructionalDisruption).filter(InstructionalDisruption.id == disruption_id))
    disruption = res.scalars().first()
    if not disruption:
        raise HTTPException(status_code=404, detail="Disruption not found.")
    await db.delete(disruption)
    await db.commit()
    return {"message": "Disruption deleted."}


@router.get("/schools/{school_id}/instructional-availability", response_model=CalendarAvailabilityOut)
async def get_instructional_availability(
    school_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    school_res = await db.execute(select(School).filter(School.id == school_id))
    school = school_res.scalars().first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")

    disruptions_res = await db.execute(select(InstructionalDisruption).filter(InstructionalDisruption.school_id == school_id))
    disruptions = disruptions_res.scalars().all()

    curriculum_res = await db.execute(select(CurriculumDay))
    curriculum = curriculum_res.scalars().all()

    metrics = calculate_pacing_metrics(school.official_working_days, 104, disruptions, curriculum)

    return CalendarAvailabilityOut(
        school_id=school.id,
        official_working_days=school.official_working_days,
        current_day=metrics["current_day"],
        total_lost_days=metrics["total_lost_days"],
        remaining_instructional_days=metrics["remaining_instructional_days"],
        pacing_buffer=metrics["pacing_buffer"],
        risk_status=metrics["risk_status"],
        risk_label=metrics["risk_label"]
    )

