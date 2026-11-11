from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from backend.app.schemas.common import BaseSchema


class CompetencyScoresSchema(BaseModel):
    LU: int
    CU: int
    AU: int
    CT: int
    overall: int


class StudentOut(BaseSchema):
    id: str
    school_id: str
    class_id: str
    class_name: str
    name: str
    roll_no: int
    gender: str
    attendance_pct: float
    competencies: CompetencyScoresSchema
    baseline_competencies: CompetencyScoresSchema
    learning_modality: str
    parent_id: Optional[str] = None
    homework_completion_rate: float
    needs_support: bool
    support_area: Optional[str] = None


class StudentProfileOut(StudentOut):
    subject_names: List[str]
    parent_names: List[str]


class ClassCompetencyAnalyticsOut(BaseSchema):
    class_id: str
    average_competencies: CompetencyScoresSchema
    baseline_comparison: CompetencyScoresSchema
    total_students: int
    needs_support_count: int
    dimension_breakdown: Dict[str, Any]


class SchoolComparisonItem(BaseSchema):
    name: str
    LU: int
    CU: int
    AU: int
    CT: int


class HomeworkOut(BaseSchema):
    id: str
    student_id: str
    student_name: str
    class_id: str
    subject_id: str
    title: str
    competency_target: str
    reason: Optional[str] = None
    description: str
    due_date: str
    status: str
    score: Optional[int] = None

