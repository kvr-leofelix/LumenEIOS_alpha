from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import get_current_user, require_roles, require_school_access
from backend.app.db.session import get_db
from backend.app.lib.class_names import parse_class_name, class_identity
from backend.app.models.entities import ClassSection, ParentStudentLink, School, Student, User, AuditEvent, utc_now
from backend.app.schemas.schools import ClassCreate, ClassSectionOut, TeacherAssignmentRequest
from backend.app.schemas.competencies import StudentOut, StudentProfileOut, CompetencyScoresSchema
from backend.app.modules.differentiated_homework.student_access import (
    require_linked_student,
    resolve_linked_student,
    subject_names,
)

router = APIRouter(prefix="/classes", tags=["Classes"])


@router.post("", response_model=ClassSectionOut, status_code=status.HTTP_201_CREATED)
async def create_class(
    body: ClassCreate,
    db: AsyncSession = Depends(get_db),
    principal: User = Depends(require_roles("principal")),
):
    try:
        grade, section, display, identity = parse_class_name(body.name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    school = (await db.execute(select(School).filter(School.id == body.school_id))).scalars().first()
    if not school:
        raise HTTPException(status_code=404, detail="School not found.")
    await require_school_access(db, principal, body.school_id)

    existing = (await db.execute(select(ClassSection).filter(ClassSection.school_id == body.school_id))).scalars().all()
    if any(class_identity(item.name) == identity for item in existing):
        raise HTTPException(status_code=409, detail="A class with this name already exists")

    created = ClassSection(
        school_id=body.school_id,
        grade=grade,
        section=section,
        name=display,
        class_teacher_id=None,
        class_teacher_name=None,
        student_count=0,
        subject_ids_json=[],
    )
    school.class_count = (school.class_count or 0) + 1
    db.add(created)
    db.add(
        AuditEvent(
            timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
            user_id=principal.id,
            user_name=principal.name,
            action="Class Created",
            details=f"{principal.name} added class {display}.",
            category="curriculum",
        )
    )
    await db.commit()
    await db.refresh(created)
    return created


@router.get("/{class_id}", response_model=ClassSectionOut)
async def get_class(class_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = await db.execute(select(ClassSection).filter(ClassSection.id == class_id))
    cls = result.scalars().first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found.")
    await require_school_access(db, current_user, cls.school_id)
    return cls


@router.post("/{class_id}/assignments", response_model=ClassSectionOut)
async def assign_teacher(
    class_id: str,
    req: TeacherAssignmentRequest,
    db: AsyncSession = Depends(get_db),
    admin_or_principal: User = Depends(require_roles("admin", "principal"))
):
    result = await db.execute(select(ClassSection).filter(ClassSection.id == class_id))
    cls = result.scalars().first()
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found.")

    cls.class_teacher_id = req.teacher_id
    cls.class_teacher_name = req.teacher_name

    audit = AuditEvent(
        timestamp=utc_now().strftime("%Y-%m-%d %H:%M"),
        user_id=admin_or_principal.id,
        user_name=admin_or_principal.name,
        action="Teacher Reassignment",
        details=f"Assigned {req.teacher_name} as lead teacher for {cls.name}",
        category="curriculum"
    )
    db.add(audit)
    await db.commit()
    await db.refresh(cls)
    return cls


def student_out(s: Student) -> StudentOut:
    return StudentOut(
        id=s.id,
        school_id=s.school_id,
        class_id=s.class_id,
        class_name=s.class_name,
        name=s.name,
        roll_no=s.roll_no,
        gender=s.gender,
        attendance_pct=s.attendance_pct,
        competencies=CompetencyScoresSchema(
            LU=s.lu_score, CU=s.cu_score, AU=s.au_score, CT=s.ct_score, overall=s.overall_score
        ),
        baseline_competencies=CompetencyScoresSchema(
            LU=s.baseline_lu, CU=s.baseline_cu, AU=s.baseline_au, CT=s.baseline_ct, overall=s.baseline_overall
        ),
        learning_modality=s.learning_modality,
        parent_id=s.parent_id,
        homework_completion_rate=s.homework_completion_rate,
        needs_support=s.needs_support,
        support_area=s.support_area,
    )


@router.get("/students/me", response_model=StudentProfileOut)
async def my_student_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles("student", authenticated=True)),
):
    student = await require_linked_student(db, current_user)
    section = await db.get(ClassSection, student.class_id)
    section = section if section and section.school_id == student.school_id else None
    subjects = await subject_names(db, section.subject_ids_json if section else [])
    parents = await db.scalars(
        select(User.name)
        .join(ParentStudentLink, ParentStudentLink.parent_user_id == User.id)
        .where(ParentStudentLink.student_id == student.id, User.role == "parent")
        .distinct()
        .order_by(User.name)
    )
    profile = student_out(student)
    if section:
        profile.class_name = section.name
    return StudentProfileOut(
        **profile.model_dump(), subject_names=sorted(set(subjects.values())), parent_names=list(parents),
    )


@router.get("/{class_id}/students", response_model=List[StudentOut])
async def list_class_students(
    class_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    section = await db.get(ClassSection, class_id)
    if not section:
        raise HTTPException(status_code=404, detail="Class not found.")
    await require_school_access(db, current_user, section.school_id)
    result = await db.execute(select(Student).filter(Student.class_id == class_id).order_by(Student.roll_no))
    return [student_out(student) for student in result.scalars()]
