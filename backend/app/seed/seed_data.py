"""LumenEIOS roster seed: IIT Mandi -> JNV Bengaluru and Dakshana Kottayam.

Hierarchy:
    Admin IIT Mandi controls both schools.
    JNV Bengaluru     -> teachers Arvind, Garima   -> students Gurleen (6), Agam (7), Pranay (8)
    Dakshana Kottayam -> teachers Kamlesh, Preeti  -> students Tanv (9), KVR (10), Grishma (11)
    Every student has one parent account ("<Name> ki Mummy").

Teachers see students through school membership, so a school's teachers see all of its students.
Each class lists the subjects its school's teachers teach at that grade.

Every account's password is demo123. Seeding runs only on an empty database; to reseed, delete
the database file (or run backend/scripts/reset_roster.py) and restart the backend.

The IDs school-1 and user-principal-1 are kept on purpose: some API fallbacks still name them.
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.security import get_password_hash
from backend.app.models.entities import (
    ClassSection,
    ParentStudentLink,
    School,
    SchoolMembership,
    Student,
    Subject,
    User,
)
from backend.app.modules.differentiated_homework.models import StudentAccountLink

logger = logging.getLogger(__name__)

DEFAULT_PASSWORD = "demo123"
DOMAIN = "lumeneios.demo"

# The LEOFELIX root login switches into these accounts (see api/v1/auth.py).
ROOT_PERSONA_EMAILS = {
    "admin": f"iitmandi@{DOMAIN}",
    "principal": f"principal.jnv@{DOMAIN}",
    "teacher": f"garima@{DOMAIN}",
    "student": f"gurleen@{DOMAIN}",
    "parent": f"gurleen.mummy@{DOMAIN}",
}

SCHOOLS = [
    {
        "id": "school-1",
        "name": "JNV Bengaluru",
        "location": "Bengaluru",
        "state": "Karnataka",
        "principal_id": "user-principal-1",
        "principal_name": "JNV Bengaluru",
        "principal_email": f"principal.jnv@{DOMAIN}",
    },
    {
        "id": "school-2",
        "name": "Dakshana Kottayam",
        "location": "Kottayam",
        "state": "Kerala",
        "principal_id": "user-principal-2",
        "principal_name": "Dakshana Kottayam",
        "principal_email": f"principal.dakshana@{DOMAIN}",
    },
]

SUBJECTS = [
    {"id": "sub-sci", "name": "Science", "code": "SCI", "grade": 6, "icon_name": "FlaskConical"},
    {"id": "sub-math", "name": "Mathematics", "code": "MATH", "grade": 6, "icon_name": "Calculator"},
    {"id": "sub-eng", "name": "English", "code": "ENG", "grade": 6, "icon_name": "BookOpen"},
    {"id": "sub-chem", "name": "Chemistry", "code": "CHEM", "grade": 11, "icon_name": "FlaskConical"},
]

TEACHERS = [
    {"key": "arvind", "name": "Arvind", "school": "school-1", "subject": "sub-chem",
     "grades": [11, 12], "designation": "Chemistry teacher, Classes 11 and 12"},
    {"key": "garima", "name": "Garima", "school": "school-1", "subject": "sub-sci",
     "grades": [6, 7, 8, 9], "designation": "Science teacher, Classes 6 to 9"},
    {"key": "kamlesh", "name": "Kamlesh", "school": "school-2", "subject": "sub-math",
     "grades": [6, 7, 8, 9], "designation": "Mathematics teacher, Classes 6 to 9"},
    {"key": "preeti", "name": "Preeti", "school": "school-2", "subject": "sub-eng",
     "grades": [6, 7, 8, 9, 10, 11], "designation": "English teacher, Classes 6 to 11"},
]

STUDENTS = [
    {"key": "gurleen", "name": "Gurleen", "school": "school-1", "grade": 6},
    {"key": "agam", "name": "Agam", "school": "school-1", "grade": 7},
    {"key": "pranay", "name": "Pranay", "school": "school-1", "grade": 8},
    {"key": "tanv", "name": "Tanv", "school": "school-2", "grade": 9},
    {"key": "kvr", "name": "KVR", "school": "school-2", "grade": 10},
    {"key": "grishma", "name": "Grishma", "school": "school-2", "grade": 11},
]

SCHOOL_SLUG = {"school-1": "jnv", "school-2": "dakshana"}


def class_id(school_id: str, grade: int) -> str:
    return f"class-{SCHOOL_SLUG[school_id]}-{grade}"


def build_classes() -> list[dict]:
    """One section per grade a school's teachers teach, listing the subjects taught there."""
    classes: dict[tuple[str, int], dict] = {}
    for teacher in TEACHERS:
        for grade in teacher["grades"]:
            entry = classes.setdefault((teacher["school"], grade), {
                "id": class_id(teacher["school"], grade),
                "school_id": teacher["school"],
                "grade": grade,
                "subject_ids": [],
                "teachers": [],
            })
            entry["subject_ids"].append(teacher["subject"])
            entry["teachers"].append(teacher)
    return sorted(classes.values(), key=lambda c: (c["school_id"], c["grade"]))


def roster_users() -> list[dict]:
    """Every login account, in display order. Used by the seed and the login sheet."""
    users = [{
        "id": "user-admin", "email": f"iitmandi@{DOMAIN}", "name": "IIT Mandi", "role": "admin",
        "school_id": "school-1", "designation": "Administrator, JNV Bengaluru and Dakshana Kottayam",
    }]
    for school in SCHOOLS:
        users.append({
            "id": school["principal_id"], "email": school["principal_email"],
            "name": school["principal_name"], "role": "principal", "school_id": school["id"],
            "designation": f"Principal, {school['name']}",
        })
    for teacher in TEACHERS:
        users.append({
            "id": f"user-teacher-{teacher['key']}", "email": f"{teacher['key']}@{DOMAIN}",
            "name": teacher["name"], "role": "teacher", "school_id": teacher["school"],
            "designation": teacher["designation"],
        })
    for student in STUDENTS:
        users.append({
            "id": f"student-{student['key']}", "email": f"{student['key']}@{DOMAIN}",
            "name": student["name"], "role": "student", "school_id": student["school"],
            "designation": f"Student, Class {student['grade']}",
        })
    for student in STUDENTS:
        users.append({
            "id": f"parent-{student['key']}", "email": f"{student['key']}.mummy@{DOMAIN}",
            "name": f"{student['name']} ki Mummy", "role": "parent", "school_id": student["school"],
            "designation": f"Parent of {student['name']}",
        })
    return users


async def seed_database_if_empty(session: AsyncSession) -> None:
    if (await session.execute(select(School.id).limit(1))).first():
        logger.info("Database already seeded.")
        return

    logger.info("Empty database detected. Seeding the IIT Mandi roster...")
    classes = build_classes()
    names = {s["id"]: s["name"] for s in SCHOOLS}

    for school in SCHOOLS:
        session.add(School(
            id=school["id"],
            name=school["name"],
            location=school["location"],
            state=school["state"],
            infrastructure_tier="standard",
            academic_year="2026-2027",
            principal_id=school["principal_id"],
            principal_name=school["principal_name"],
            student_count=sum(1 for s in STUDENTS if s["school"] == school["id"]),
            teacher_count=sum(1 for t in TEACHERS if t["school"] == school["id"]),
            class_count=sum(1 for c in classes if c["school_id"] == school["id"]),
            pacing_risk="low",
            description=f"{school['name']}, administered by IIT Mandi.",
        ))

    for subject in SUBJECTS:
        session.add(Subject(**subject))

    password_hash = get_password_hash(DEFAULT_PASSWORD)
    for user in roster_users():
        session.add(User(**user, hashed_password=password_hash))
        session.add(SchoolMembership(
            id=f"mem-{user['id']}-{user['school_id']}", user_id=user["id"],
            school_id=user["school_id"], role=user["role"],
        ))
    # The admin controls both schools.
    session.add(SchoolMembership(id="mem-user-admin-school-2", user_id="user-admin", school_id="school-2", role="admin"))

    for section in classes:
        lead = section["teachers"][0]
        session.add(ClassSection(
            id=section["id"],
            school_id=section["school_id"],
            grade=section["grade"],
            section="A",
            name=f"Class {section['grade']}-A",
            class_teacher_id=f"user-teacher-{lead['key']}",
            class_teacher_name=lead["name"],
            student_count=sum(1 for s in STUDENTS if s["school"] == section["school_id"] and s["grade"] == section["grade"]),
            subject_ids_json=section["subject_ids"],
        ))

    # Flush parents of the foreign keys before the rows that point at them.
    await session.flush()

    for student in STUDENTS:
        student_id = f"student-{student['key']}"
        parent_id = f"parent-{student['key']}"
        session.add(Student(
            id=student_id,
            school_id=student["school"],
            class_id=class_id(student["school"], student["grade"]),
            class_name=f"Class {student['grade']}-A",
            name=student["name"],
            roll_no=1,
            parent_id=parent_id,
        ))
    await session.flush()

    for student in STUDENTS:
        student_id = f"student-{student['key']}"
        session.add(ParentStudentLink(id=f"psl-{student['key']}", parent_user_id=f"parent-{student['key']}", student_id=student_id))
        session.add(StudentAccountLink(user_id=student_id, student_id=student_id, created_by="user-admin"))

    await session.commit()
    logger.info(
        "Seeded %d schools (%s), %d accounts, %d classes.",
        len(SCHOOLS), ", ".join(names.values()), len(roster_users()), len(classes),
    )
