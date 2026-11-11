from typing import Optional, List, Any
from pydantic import BaseModel, Field
from backend.app.schemas.common import BaseSchema


class QuestionSchema(BaseSchema):
    id: Optional[str] = None
    text: str
    type: str  # mcq, short, descriptive, practical
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    marking_rubric: Optional[str] = None
    marks: int = 1
    competency: str  # LU, CU, AU, CT
    bloom_level: str  # Remember, Understand, Apply, Analyze, Evaluate, Create
    source_document_ids: Optional[List[str]] = None
    source_document_names: Optional[List[str]] = None
    is_ai_generated: Optional[bool] = False


class GenerateQuestionsRequest(BaseModel):
    subject_id: str
    subject_name: Optional[str] = None
    source_document_ids: List[str] = []
    # Learning-resource links (Wikipedia, BYJU'S, ...) used with or instead of the chapter PDF.
    source_urls: List[str] = []
    mcq_count: int = 3
    theory_count: int = 2
    bloom_level: str = "Apply"
    focus_topic: Optional[str] = None
    save_to_bank: bool = True


class QuestionUpdateRequest(BaseModel):
    text: Optional[str] = None
    type: Optional[str] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    marking_rubric: Optional[str] = None
    marks: Optional[int] = None
    competency: Optional[str] = None
    bloom_level: Optional[str] = None


class AssessmentCreate(BaseModel):
    class_id: Optional[str] = None
    subject_id: str
    title: str
    cycle_number: int = 1
    date: str
    duration_minutes: int = 45
    total_marks: int = 25
    questions: List[QuestionSchema] = Field(min_length=1)
    competency_focus: List[str]


class AssessmentOut(BaseSchema):
    id: str
    school_id: str
    class_id: str
    subject_id: str
    title: str
    cycle_number: int
    date: str
    duration_minutes: int
    total_marks: int
    status: str
    competency_focus_json: List[str]
    questions_json: List[Any]


class AssignmentSubject(BaseModel):
    id: str
    name: str


class AssignmentTarget(BaseModel):
    id: str
    name: str
    subjects: List[AssignmentSubject]


class UploadQuestion(BaseModel):
    id: Optional[str] = None
    text: str
    type: str
    options: Optional[List[str]] = None
    marks: int
    competency: Optional[str] = None


class UploadAssignment(BaseModel):
    id: str
    title: str
    date: str
    class_name: str
    subject_name: str
    total_marks: int
    uploaded: bool
    questions: List[UploadQuestion]


class SubmissionCreate(BaseModel):
    student_id: str
    marks_obtained: int
    total_marks: int
    lu_score: int
    cu_score: int
    au_score: int
    ct_score: int
    feedback: Optional[str] = None
    is_scanned: bool = False


class SubmissionOut(BaseSchema):
    id: str
    assessment_id: str
    student_id: str
    student_name: str
    marks_obtained: int
    total_marks: int
    percentage: int
    scores: dict
    feedback: Optional[str] = None
    submission_date: str
    is_scanned: bool
