from enum import Enum
from typing import List, Optional
from fastapi import HTTPException, status


class RoleEnum(str, Enum):
    ADMIN = "admin"
    PRINCIPAL = "principal"
    TEACHER = "teacher"
    STUDENT = "student"
    PARENT = "parent"


# Permission constants
PERM_MANAGE_SCHOOLS = "manage_schools"
PERM_MANAGE_USERS = "manage_users"
PERM_VIEW_GLOBAL = "view_global_analytics"
PERM_ASSIGN_TEACHERS = "assign_teachers"
PERM_CREATE_ASSESSMENT = "create_assessment"
PERM_GRADE_ASSESSMENT = "grade_assessment"
PERM_RECORD_DISRUPTIONS = "record_disruptions"
PERM_COMPRESS_SYLLABUS = "compress_syllabus"
PERM_VERIFY_OCR = "verify_ocr"
PERM_VIEW_STUDENT_DATA = "view_student_data"
PERM_SUBMIT_HOMEWORK = "submit_homework"

ROLE_PERMISSIONS = {
    RoleEnum.ADMIN: [
        PERM_MANAGE_SCHOOLS,
        PERM_MANAGE_USERS,
        PERM_VIEW_GLOBAL,
        PERM_ASSIGN_TEACHERS,
        PERM_CREATE_ASSESSMENT,
        PERM_GRADE_ASSESSMENT,
        PERM_RECORD_DISRUPTIONS,
        PERM_COMPRESS_SYLLABUS,
        PERM_VERIFY_OCR,
        PERM_VIEW_STUDENT_DATA,
    ],
    RoleEnum.PRINCIPAL: [
        PERM_ASSIGN_TEACHERS,
        PERM_CREATE_ASSESSMENT,
        PERM_RECORD_DISRUPTIONS,
        PERM_COMPRESS_SYLLABUS,
        PERM_VIEW_STUDENT_DATA,
    ],
    RoleEnum.TEACHER: [
        PERM_CREATE_ASSESSMENT,
        PERM_GRADE_ASSESSMENT,
        PERM_RECORD_DISRUPTIONS,
        PERM_COMPRESS_SYLLABUS,
        PERM_VERIFY_OCR,
        PERM_VIEW_STUDENT_DATA,
    ],
    RoleEnum.STUDENT: [
        PERM_SUBMIT_HOMEWORK,
    ],
    RoleEnum.PARENT: [
        PERM_VIEW_STUDENT_DATA,
    ],
}


def has_role_permission(role: str, permission: str) -> bool:
    try:
        r = RoleEnum(role)
        return permission in ROLE_PERMISSIONS.get(r, [])
    except ValueError:
        return False


def enforce_permission(user_role: str, permission: str):
    if not has_role_permission(user_role, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation not permitted for role '{user_role}'. Required permission: '{permission}'."
        )


def enforce_school_access(user, target_school_id: str):
    """
    Ensure the user is authorized to access the requested school.
    Admins can access any school.
    Principals/Teachers/Students/Parents must match their school_id or membership.
    """
    if user.role == RoleEnum.ADMIN.value:
        return True
    if user.school_id == target_school_id:
        return True
    
    # Check memberships list if available
    memberships = getattr(user, "memberships", [])
    if any(m.school_id == target_school_id for m in memberships):
        return True

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Cross-school tenant access denied. You are not authorized for this campus."
    )

