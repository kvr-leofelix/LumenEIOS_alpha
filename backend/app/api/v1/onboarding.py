from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.dependencies import require_roles
from backend.app.core.security import get_password_hash
from backend.app.db.session import get_db
from backend.app.models.entities import (
    ClassSection, School, SchoolMembership, Student, User, UserProfile,
)
from backend.app.modules.differentiated_homework.models import StudentAccountLink
from backend.app.schemas.auth import UserOut
from backend.app.schemas.schools import SchoolOut

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


class AccountDetails(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    phone: str | None = Field(None, max_length=40)
    address: str | None = Field(None, max_length=1000)
    date_of_birth: date | None = None

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must fit within 72 UTF-8 bytes.")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def validate_birth_date(cls, value: date | None) -> date | None:
        if value and value > date.today():
            raise ValueError("Date of birth cannot be in the future.")
        return value


class StudentDetails(AccountDetails):
    class_id: str = Field(min_length=1, max_length=64)
    roll_no: int = Field(gt=0, le=2_147_483_647)
    gender: Literal["M", "F", "Other"] = "Other"


class TeacherDetails(AccountDetails):
    designation: str | None = Field(None, max_length=255)


class SchoolDetails(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    location: str = Field(min_length=1, max_length=255)
    state: str = Field(min_length=1, max_length=100)
    infrastructure_tier: Literal["high-tech", "standard", "low-tech"]
    academic_year: str = Field(min_length=1, max_length=50)
    official_working_days: int = Field(220, gt=0, le=366)
    principal: AccountDetails


async def add_account(
    db: AsyncSession, details: AccountDetails, role: str, school_id: str,
    designation: str | None = None,
) -> User:
    email = details.email.lower()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="This login email is already registered.")

    user = User(
        name=details.name, email=email, hashed_password=get_password_hash(details.password),
        role=role, school_id=school_id, designation=designation,
    )
    db.add(user)
    await db.flush()
    db.add_all([
        SchoolMembership(user_id=user.id, school_id=school_id, role=role),
        UserProfile(
            user_id=user.id, phone=details.phone, address=details.address,
            date_of_birth=details.date_of_birth,
        ),
    ])
    return user


async def active_school_id(db: AsyncSession, actor: User) -> str:
    school_id = await db.scalar(
        select(School.id).where(School.id == actor.school_id, School.is_archived.is_(False))
    )
    if not school_id:
        raise HTTPException(status_code=403, detail="Your account needs an active school.")
    return school_id


@router.post("/students", response_model=UserOut, status_code=201)
async def add_student(
    details: StudentDetails,
    db: AsyncSession = Depends(get_db),
    teacher: User = Depends(require_roles("teacher", authenticated=True)),
):
    school_id = await active_school_id(db, teacher)
    # Lock the section via its count update so two requests cannot claim the same roll number.
    section = (await db.execute(
        update(ClassSection)
        .where(ClassSection.id == details.class_id, ClassSection.school_id == school_id)
        .values(student_count=ClassSection.student_count + 1)
        .returning(ClassSection.name)
    )).scalar_one_or_none()
    if section is None:
        raise HTTPException(status_code=404, detail="Class section not found in your school.")
    if await db.scalar(select(Student.id).where(
        Student.class_id == details.class_id, Student.roll_no == details.roll_no,
    )):
        raise HTTPException(status_code=409, detail="This roll number already exists in the selected class.")

    try:
        user = await add_account(db, details, "student", school_id)
        student = Student(
            school_id=school_id, class_id=details.class_id, class_name=section,
            name=details.name, roll_no=details.roll_no, gender=details.gender,
        )
        db.add(student)
        await db.flush()
        db.add(StudentAccountLink(user_id=user.id, student_id=student.id, created_by=teacher.id))
        await db.execute(update(School).where(School.id == school_id)
                         .values(student_count=School.student_count + 1))
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Could not save the student. Check for a duplicate account.") from exc
    return user


@router.post("/teachers", response_model=UserOut, status_code=201)
async def add_teacher(
    details: TeacherDetails,
    db: AsyncSession = Depends(get_db),
    principal: User = Depends(require_roles("principal", authenticated=True)),
):
    school_id = await active_school_id(db, principal)
    try:
        user = await add_account(db, details, "teacher", school_id, details.designation)
        await db.execute(update(School).where(School.id == school_id)
                         .values(teacher_count=School.teacher_count + 1))
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Could not save the teacher. Check for a duplicate account.") from exc
    return user


@router.post("/schools", response_model=SchoolOut, status_code=201)
async def add_school(
    details: SchoolDetails,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles("admin", authenticated=True)),
):
    try:
        school = School(**details.model_dump(exclude={"principal"}), principal_name=details.principal.name)
        db.add(school)
        await db.flush()
        principal = await add_account(db, details.principal, "principal", school.id, "Principal")
        school.principal_id = principal.id
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Could not save the school. Check the principal's login email.") from exc
    return school
