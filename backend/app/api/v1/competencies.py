from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_user, require_school_access, user_school_ids
from backend.app.db.session import get_db
from backend.app.models.entities import Student, School, ClassSection, User, ParentStudentLink
from backend.app.schemas.competencies import (
    CompetencyScoresSchema,
    StudentOut,
    ClassCompetencyAnalyticsOut,
    SchoolComparisonItem,
)
from backend.app.services.competency_service import aggregate_student_competencies

router = APIRouter(tags=["Competencies & Analytics"])


@router.get("/students/{student_id}/competencies", response_model=CompetencyScoresSchema)
async def get_student_competencies(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Enforce record-level authorization
    if current_user.role == "student" and current_user.id != student_id:
        raise HTTPException(status_code=403, detail="Access denied. Students can only view their own competency scores.")
    if current_user.role == "parent":
        # Check linked child
        linked = await db.scalar(select(ParentStudentLink.id).where(
            ParentStudentLink.parent_user_id == current_user.id,
            ParentStudentLink.student_id == student_id,
        ))
        if not linked:
            raise HTTPException(status_code=403, detail="Access denied. Parents can only view their linked children.")

    st_res = await db.execute(select(Student).filter(Student.id == student_id))
    st = st_res.scalars().first()
    if not st:
        raise HTTPException(status_code=404, detail="Student not found.")
    if current_user.role not in ("student", "parent"):
        await require_school_access(db, current_user, st.school_id)

    return CompetencyScoresSchema(
        LU=st.lu_score,
        CU=st.cu_score,
        AU=st.au_score,
        CT=st.ct_score,
        overall=st.overall_score
    )


@router.get("/classes/{class_id}/competency-analytics", response_model=ClassCompetencyAnalyticsOut)
async def get_class_competency_analytics(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    section = await db.get(ClassSection, class_id)
    if not section:
        raise HTTPException(status_code=404, detail="Class not found.")
    await require_school_access(db, current_user, section.school_id)
    st_res = await db.execute(select(Student).filter(Student.class_id == class_id))
    students = st_res.scalars().all()

    avg = aggregate_student_competencies(students)
    needs_support = sum(1 for s in students if s.needs_support)

    return ClassCompetencyAnalyticsOut(
        class_id=class_id,
        average_competencies=CompetencyScoresSchema(**avg),
        baseline_comparison=CompetencyScoresSchema(LU=68, CU=70, AU=62, CT=58, overall=65),
        total_students=len(students),
        needs_support_count=needs_support,
        dimension_breakdown={
            "LU": {"proficient": sum(1 for s in students if s.lu_score >= 70)},
            "CU": {"proficient": sum(1 for s in students if s.cu_score >= 70)},
            "AU": {"proficient": sum(1 for s in students if s.au_score >= 70)},
            "CT": {"proficient": sum(1 for s in students if s.ct_score >= 70)},
        }
    )


@router.get("/schools/{school_id}/competency-analytics")
async def get_school_competency_analytics(
    school_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await require_school_access(db, current_user, school_id)
    st_res = await db.execute(select(Student).filter(Student.school_id == school_id))
    students = st_res.scalars().all()
    avg = aggregate_student_competencies(students)
    return {
        "school_id": school_id,
        "averages": avg,
        "total_evaluated_students": len(students)
    }


@router.get("/analytics/school-comparison", response_model=List[SchoolComparisonItem])
async def get_school_comparison(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Averages from real student records, limited to the schools the viewer can see.
    query = select(School).filter(School.is_archived == False).order_by(School.name)  # noqa: E712
    schools = [s for s in (await db.execute(query)).scalars()]
    if current_user.role != "admin":
        allowed = await user_school_ids(db, current_user)
        schools = [s for s in schools if s.id in allowed]
    items = []
    for school in schools:
        students = (await db.execute(select(Student).filter(Student.school_id == school.id))).scalars().all()
        avg = aggregate_student_competencies(students)
        items.append(SchoolComparisonItem(name=school.name, LU=avg["LU"], CU=avg["CU"], AU=avg["AU"], CT=avg["CT"]))
    return items

