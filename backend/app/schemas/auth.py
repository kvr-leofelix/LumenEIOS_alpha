from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr, Field, field_validator
from backend.app.schemas.common import BaseSchema


class LoginRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255)  # Also accepts the development root username.
    password: str


class UserOut(BaseSchema):
    id: str
    email: str
    name: str
    role: str
    school_id: Optional[str] = None
    designation: Optional[str] = None
    avatar: Optional[str] = None
    assigned_class_ids: List[str] = []
    assigned_subject_ids: List[str] = []
    linked_child_ids: List[str] = []
    demo_root: bool = False


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class SwitchSchoolRequest(BaseModel):
    school_id: str


class UserCreate(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str
    school_id: Optional[str] = None
    designation: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must fit within 72 UTF-8 bytes.")
        return value


class UserUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    school_id: Optional[str] = None
    designation: Optional[str] = None
    avatar: Optional[str] = None

