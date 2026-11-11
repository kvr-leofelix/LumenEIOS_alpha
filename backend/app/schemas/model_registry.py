from typing import Optional, List, Any
from pydantic import BaseModel
from backend.app.schemas.common import BaseSchema


class ModelEvaluationOut(BaseSchema):
    id: str
    model_id: str
    model_version: str
    cer: float
    wer: float
    field_accuracy: float
    latency_ms: int
    status: str
    notes: Optional[str] = None
    evaluated_at: Any


class ModelDeploymentOut(BaseSchema):
    id: str
    model_id: str
    model_version: str
    provider: str
    is_active: bool
    deployed_by: str
    deployed_at: Any
    rollback_reason: Optional[str] = None


class ModelRollbackRequest(BaseModel):
    rollback_reason: str
    target_version: Optional[str] = None

