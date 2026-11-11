from typing import Optional, List, Any
from pydantic import BaseModel
from backend.app.schemas.common import BaseSchema


class CalculatePacingRequest(BaseModel):
    core_ratio: float = 0.60
    current_day: int = 104
    total_official_days: int = 180


class PacingMetricsOut(BaseSchema):
    total_official_days: int
    current_day: int
    total_lost_days: float
    remaining_instructional_days: float
    core_concepts_remaining: int
    supplementary_topics_remaining: int
    total_periods_needed_original: int
    pacing_buffer: float
    risk_status: str
    risk_label: str


class TopicSummary(BaseSchema):
    id: str
    day_number: int
    topic: str
    objective: str
    classification: str
    estimated_duration_mins: int


class CompressionProposalOut(BaseSchema):
    proposal_id: str
    original_duration_days: int
    revised_duration_days: int
    days_saved: int
    topics_preserved_count: int
    topics_reassigned_count: int
    topics_integrated_count: int
    preserved_core_count: int
    reassigned_topics: List[TopicSummary]
    integrated_topics: List[TopicSummary]
    trade_off_analysis: List[str]
    remediation_requirements: List[str]


class ProposalDecisionRequest(BaseModel):
    notes: Optional[str] = None


class CrossCurricularProposalOut(BaseSchema):
    id: str
    title: str
    subject_ids: List[str]
    subject_names: List[str]
    target_day_numbers: List[int]
    learning_objectives: List[str]
    activity: str
    vark_modality: str
    bloom_level: str
    estimated_duration_hours: float
    time_saved_hours: float
    status: str

