from pydantic import BaseModel, EmailStr


class TeacherCreate(BaseModel):
    name: str
    email: EmailStr
    designation: str = "Teacher"
    school_id: str
