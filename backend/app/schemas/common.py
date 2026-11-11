from typing import Optional, List, Any
from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class NotificationOut(BaseSchema):
    id: str
    user_id: str
    title: str
    message: str
    type: str
    is_read: bool
    link: Optional[str] = None
    created_at: Any


class AnnouncementCreate(BaseSchema):
    title: str
    content: str
    target_role: str = "teacher"


class AnnouncementOut(BaseSchema):
    id: str
    school_id: str
    sender_id: str
    sender_name: str
    title: str
    content: str
    target_role: str
    created_at: Any


class AuditEventOut(BaseSchema):
    id: str
    timestamp: str
    user_id: str
    user_name: str
    action: str
    details: str
    category: str
    ip_address: Optional[str] = None

