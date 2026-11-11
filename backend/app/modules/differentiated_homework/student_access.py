"""Student identity and student-facing homework views.

A student is identified only through an explicit StudentAccountLink. Never
by matching User.id to Student.id, and never by email (Student has no email field).

resolve_linked_student fails closed. It returns None unless all of these hold:
- the user's role is exactly "student";
- a link exists for this user;
- the linked Student exists;
- the student's school still matches the account's school.
"""
from typing import Dict, Iterable, List, Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import Student, Subject, User
from backend.app.modules.differentiated_homework.draft_service import as_utc
from backend.app.modules.differentiated_homework.models import HomeworkAssignmentRecord, StudentAccountLink
from backend.app.modules.differentiated_homework.schemas import (
    StudentAssignmentItemOut,
    StudentAssignmentOut,
    StudentAssignmentSummaryOut,
)


async def resolve_linked_student(db: AsyncSession, user: User) -> Optional[Student]:
    if user.role != "student":
        return None
    row = (await db.execute(
        select(Student)
        .join(StudentAccountLink, StudentAccountLink.student_id == Student.id)
        .filter(StudentAccountLink.user_id == user.id)
    )).scalars().first()
    if row is None:
        return None
    if not user.school_id or user.school_id != row.school_id:
        return None
    return row


async def require_linked_student(db: AsyncSession, user: User) -> Student:
    student = await resolve_linked_student(db, user)
    if not student:
        raise HTTPException(status_code=404, detail="Your login is not linked to a student profile.")
    return student


async def subject_names(db: AsyncSession, subject_ids: Iterable[str]) -> Dict[str, str]:
    ids = set(subject_ids)
    if not ids:
        return {}
    rows = await db.execute(select(Subject.id, Subject.name).filter(Subject.id.in_(ids)))
    return {r.id: r.name for r in rows.all()}


def to_student_summary(assignment: HomeworkAssignmentRecord, names: Dict[str, str]) -> StudentAssignmentSummaryOut:
    return StudentAssignmentSummaryOut(
        id=assignment.id,
        subject_id=assignment.subject_id,
        subject_name=names.get(assignment.subject_id),
        status=assignment.status,
        assigned_at=as_utc(assignment.assigned_at),
        due_at=as_utc(assignment.due_at),
        question_count=assignment.draft.question_count,
        total_marks=assignment.draft.total_marks,
    )


def to_student_detail(assignment: HomeworkAssignmentRecord, names: Dict[str, str]) -> StudentAssignmentOut:
    items: List[StudentAssignmentItemOut] = [
        StudentAssignmentItemOut(
            position=i.position, text=i.text, type=i.type, options=list(i.options_json or []), marks=i.marks,
        )
        for i in sorted(assignment.draft.items, key=lambda i: i.position)
    ]
    return StudentAssignmentOut(**to_student_summary(assignment, names).model_dump(), items=items)
