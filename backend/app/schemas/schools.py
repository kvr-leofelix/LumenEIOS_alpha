from typing import Optional, List, Any
from pydantic import BaseModel
from backend.app.schemas.common import BaseSchema


class SchoolCreate(BaseModel):
    name: str
    location: str
    state: str
    infrastructure_tier: str
    academic_year: str = "2026-2027"
    principal_name: Optional[str] = None
    student_count: int = 0
    teacher_count: int = 0
    class_count: int = 0
    description: Optional[str] = None
    official_working_days: int = 220


class SchoolUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    state: Optional[str] = None
    infrastructure_tier: Optional[str] = None
    principal_name: Optional[str] = None
    student_count: Optional[int] = None
    teacher_count: Optional[int] = None
    class_count: Optional[int] = None
    pacing_risk: Optional[str] = None
    description: Optional[str] = None
    official_working_days: Optional[int] = None


class SchoolOut(BaseSchema):
    id: str
    name: str
    location: str
    state: str
    infrastructure_tier: str
    academic_year: str
    principal_id: Optional[str] = None
    principal_name: Optional[str] = None
    student_count: int
    teacher_count: int
    class_count: int
    pacing_risk: str
    description: Optional[str] = None
    official_working_days: int
    is_archived: bool


class ClassCreate(BaseModel):
    school_id: str
    name: str


class ClassSectionOut(BaseSchema):
    id: str
    school_id: str
    grade: int
    section: str
    name: str
    class_teacher_id: Optional[str] = None
    class_teacher_name: Optional[str] = None
    student_count: int
    subject_ids_json: List[str]


class TeacherAssignmentRequest(BaseModel):
    teacher_id: str
    teacher_name: str

