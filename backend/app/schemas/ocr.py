from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, field_validator
from backend.app.schemas.common import BaseSchema


class DocumentOut(BaseSchema):
    id: str
    file_name: str
    file_size: int
    mime_type: str
    page_count: int
    status: str
    subject_id: Optional[str] = None
    doc_type: Optional[str] = "source_material"
    content_hash: Optional[str] = None
    created_at: Any


class BulkDocumentItemResult(BaseModel):
    file_name: str
    file_size: int
    valid: bool
    duplicate: bool = False
    status: str
    error: Optional[str] = None
    document: Optional[DocumentOut] = None


class BulkDocumentUploadResponse(BaseModel):
    total_selected: int
    uploaded_count: int
    duplicate_count: int
    failed_count: int
    items: List[BulkDocumentItemResult]


class OCRAnswerRegion(BaseModel):
    item_index: int
    bounding_box: List[float]  # [ymin, xmin, ymax, xmax] normalized
    extracted_text: str
    confidence: float
    suggested_marks: int
    max_marks: int
    target_competency: str


class OCRRunOut(BaseSchema):
    id: str
    document_id: str
    provider: str
    model_version: str
    confidence_score: float
    status: str
    regions: List[OCRAnswerRegion]
    created_at: Any


class OCRPreviewItem(BaseModel):
    file_name: str
    extracted_text: str
    pages_processed: int


class OCRPreviewOut(BaseModel):
    provider: str
    model_version: str
    results: List[OCRPreviewItem]


class StudentOcrHistoryOut(OCRPreviewItem, BaseSchema):
    id: str
    created_at: datetime
    assignment_title: str | None = None

    @field_validator("created_at")
    @classmethod
    def use_utc_for_naive_timestamp(cls, value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class VerifiedItemRequest(BaseModel):
    item_index: int
    marks: int
    text: str
    feedback: Optional[str] = None


class HumanReviewRequest(BaseModel):
    document_id: str
    student_id: str
    assessment_id: str
    verified_items: List[VerifiedItemRequest]
    teacher_notes: Optional[str] = None


class HumanReviewOut(BaseSchema):
    id: str
    ocr_run_id: str
    reviewer_id: str
    student_id: str
    assessment_id: str
    verified_marks: int
    total_marks: int
    status: str
    reviewed_at: Any


class BatchItemOut(BaseSchema):
    id: str
    batch_id: str
    document_id: Optional[str] = None
    file_name: str
    file_size: int
    mime_type: str
    page_count: int
    page_range: Optional[str] = None
    status: str
    stage_progress: int
    error_message: Optional[str] = None
    student_id: Optional[str] = None
    student_name: Optional[str] = None
    student_confidence: float = 0.0
    ocr_confidence: float = 0.0
    question_evaluations_json: List[Dict[str, Any]] = []
    marks_obtained: int = 0
    max_marks: int = 25
    percentage: int = 0
    grade: str = "B"
    competency_scores_json: Dict[str, Any] = {}
    requires_review: bool = False
    review_reasons_json: List[str] = []
    is_approved: bool = False
    submission_id: Optional[str] = None
    retry_count: int = 0
    created_at: Any


class GradingBatchOut(BaseSchema):
    id: str
    school_id: str
    class_id: str
    subject_id: str
    assessment_id: str
    created_by: str
    status: str
    total_files: int
    valid_files: int
    invalid_or_duplicate_files: int
    completed_files: int
    review_required_files: int
    failed_files: int
    concurrency_limit: int
    overall_progress_pct: int = 0
    items: List[BatchItemOut] = []
    created_at: Any


class BatchItemUpdateRequest(BaseModel):
    student_id: Optional[str] = None
    marks_obtained: Optional[int] = None
    question_evaluations: Optional[List[Dict[str, Any]]] = None
    clear_review_flag: bool = True
