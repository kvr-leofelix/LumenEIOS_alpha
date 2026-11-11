from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import Assessment, ClassSection, Student, Subject, User
from backend.app.modules.differentiated_homework.student_access import require_linked_student


async def validate_assignment_target(
    db: AsyncSession, school_id: str | None, class_id: str, subject_id: str,
) -> ClassSection:
    section = await db.get(ClassSection, class_id)
    if not section or section.school_id != school_id:
        raise HTTPException(status_code=404, detail="Choose a class in your school.")
    if subject_id not in section.subject_ids_json or not await db.get(Subject, subject_id):
        raise HTTPException(status_code=422, detail="The selected class does not study this subject.")
    return section


async def upload_assignments(
    db: AsyncSession, actor: User, assessment_id: str | None = None,
) -> tuple[Student | None, list[tuple[Assessment, ClassSection, Subject]]]:
    if actor.role not in {"student", "teacher"}:
        raise HTTPException(status_code=403, detail="Upload Beta is available to students and teachers.")
    student = await require_linked_student(db, actor) if actor.role == "student" else None
    query = (
        select(Assessment, ClassSection, Subject)
        .join(ClassSection, Assessment.class_id == ClassSection.id)
        .join(Subject, Assessment.subject_id == Subject.id)
        .where(
            Assessment.school_id == actor.school_id,
            ClassSection.school_id == actor.school_id,
            Assessment.status == "scheduled",
        )
    )
    if student:
        query = query.where(Assessment.class_id == student.class_id)
    if assessment_id is not None:
        query = query.where(Assessment.id == assessment_id)
    rows = (await db.execute(query.order_by(Assessment.created_at.desc(), Assessment.id))).all()
    eligible = [
        (assessment, section, subject) for assessment, section, subject in rows
        if subject.id in section.subject_ids_json
    ]
    if assessment_id is not None and not eligible:
        raise HTTPException(status_code=404, detail="This assignment is unavailable for your class and subject.")
    return student, eligible
