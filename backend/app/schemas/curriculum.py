from typing import Optional, List, Any
from pydantic import BaseModel
from backend.app.schemas.common import BaseSchema


class CurriculumDayOut(BaseSchema):
    id: str
    day_number: int
    class_id: str
    subject_id: str
    topic: str
    objective: str
    teaching_process: str
    measurable_outcome: str
    estimated_duration_mins: int
    vark_modality: str
    bloom_level: str
    classification: str
    status: str
    prerequisites_json: List[str]


class LessonCompleteRequest(BaseModel):
    actual_duration_mins: Optional[int] = None
    teacher_notes: Optional[str] = None

