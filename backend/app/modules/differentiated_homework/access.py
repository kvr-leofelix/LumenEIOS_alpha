"""Record-level access rules for reading a student's homework data.

Rules, based only on relationships that already exist in the database:
- admin: any student. Matches the existing admin rule in get_current_school_context.
- principal, teacher: students in a school they're authorized for. Either the user's own
  school_id, or an active SchoolMembership for that school. Matches get_current_school_context.
  There's no reliable teacher-to-class assignment, so access is per school, not per class.
- parent: only students linked through ParentStudentLink.
- student: denied. No approved link exists between a student login (User) and a Student
  record, so a student can't be safely identified as "themselves" yet.
- any other role: denied.

Saved drafts have their own rules; see can_access_draft below.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import ParentStudentLink, SchoolMembership, Student, User

EDUCATOR_ROLES = {"principal", "teacher"}
ROLES_THAT_MAY_VIEW = {"admin", "parent"} | EDUCATOR_ROLES


def role_may_view_students(user: User) -> bool:
    """False for roles that can never view student data here, such as student."""
    return user.role in ROLES_THAT_MAY_VIEW


# Generating homework is an educator action, matching require_roles("admin", "principal",
# "teacher") on homework creation. Parents may view their child's analysis, but not generate.
ROLES_THAT_MAY_GENERATE = {"admin"} | EDUCATOR_ROLES


def role_may_generate_homework(user: User) -> bool:
    return user.role in ROLES_THAT_MAY_GENERATE


async def has_school_access(db: AsyncSession, user: User, school_id: str) -> bool:
    """Educator school rule: own school_id, or an active SchoolMembership. Admin: any school."""
    if user.role == "admin":
        return True
    if user.role not in EDUCATOR_ROLES:
        return False
    if user.school_id and user.school_id == school_id:
        return True
    membership = await db.execute(
        select(SchoolMembership.id).filter(
            SchoolMembership.user_id == user.id,
            SchoolMembership.school_id == school_id,
            SchoolMembership.is_active == True,  # noqa: E712 (SQL comparison)
        )
    )
    return membership.first() is not None


async def can_view_student(db: AsyncSession, user: User, student: Student) -> bool:
    """Return True if the user may read this student's homework data."""
    if user.role == "admin" or user.role in EDUCATOR_ROLES:
        return await has_school_access(db, user, student.school_id)

    if user.role == "parent":
        link = await db.execute(
            select(ParentStudentLink.id).filter(
                ParentStudentLink.parent_user_id == user.id,
                ParentStudentLink.student_id == student.id,
            )
        )
        return link.first() is not None

    return False


# --- Saved homework drafts ------------------------------------------------------------
# Drafts aren't assigned yet, so parents and students can't see them at all.
# - admin: any draft
# - principal: drafts in a school they have access to
# - teacher: only drafts they created, and only while they still have access to that school
# The same rules apply to viewing and changing (review actions and edits). A teacher can
# review their own draft, which is the "teacher review" step in the agreed flow.


async def can_access_draft(db: AsyncSession, user: User, draft) -> bool:
    if user.role == "admin":
        return True
    if user.role == "principal":
        return await has_school_access(db, user, draft.school_id)
    if user.role == "teacher":
        return draft.created_by == user.id and await has_school_access(db, user, draft.school_id)
    return False


# --- Assignments ----------------------------------------------------------------------
# Same rules as the source draft: a teacher sees assignments for drafts they created (even if a
# principal did the assigning), principals their schools, admin all. There's no approved link
# from a student login to a Student record, so students and parents get nothing here yet.


async def can_access_assignment(db: AsyncSession, user: User, assignment) -> bool:
    return await can_access_draft(db, user, assignment.draft)
