from typing import Optional, List, Any
from pydantic import BaseModel
from backend.app.schemas.common import BaseSchema


class DisruptionCreate(BaseModel):
    date: str
    reason: str
    days_lost: float
    notes: Optional[str] = None


class DisruptionOut(BaseSchema):
    id: str
    school_id: str
    date: str
    reason: str
    days_lost: float
    recorded_by: str
    notes: Optional[str] = None
    created_at: Any


class CalendarAvailabilityOut(BaseSchema):
    school_id: str
    official_working_days: int
    current_day: int
    total_lost_days: float
    remaining_instructional_days: float
    pacing_buffer: float
    risk_status: str
    risk_label: str

