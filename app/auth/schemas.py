import re
from datetime import date, time, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator
from app.utils.date_parser import parse_date_input


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    fullname: str
    date_of_birth: date
    city_of_birth: str
    time_of_birth: Optional[time] = None
    profile_picture_url: Optional[str] = None

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("يجب أن تتكون كلمة المرور من 8 أحرف على الأقل")
        if not re.search(r"[A-Z]", v):
            raise ValueError("يجب أن تحتوي كلمة المرور على حرف كبير واحد على الأقل")
        if not re.search(r"[0-9]", v):
            raise ValueError("يجب أن تحتوي كلمة المرور على رقم واحد على الأقل")
        return v

    @field_validator("fullname")
    @classmethod
    def validate_name(cls, v):
        if not v or len(v.strip()) < 2:
            raise ValueError("يجب أن يتكون الاسم من حرفين على الأقل")
        if not re.match(r"^[\u0600-\u06FF\s]+$", v.strip()):
            raise ValueError("يجب أن يكون الاسم باللغة العربية فقط")
        return v.strip()

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def normalize_date_of_birth(cls, v):
        return parse_date_input(v)


class UserResponse(BaseModel):
    id: UUID
    email: str
    fullname: str
    date_of_birth: date
    city_of_birth: str
    time_of_birth: Optional[time] = None
    is_active: bool
    is_admin: bool
    is_verified: bool
    profile_picture_url: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RegisterResponse(BaseModel):
    message: str
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Optional[UserResponse] = None


class ForgetPasswordRequest(BaseModel):
    email: EmailStr


class ForgetPasswordResponse(BaseModel):
    message: str


class VerifyResetCodeRequest(BaseModel):
    verification_code: str


class VerifyResetCodeResponse(BaseModel):
    is_valid: bool
    message: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    verification_code: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("يجب أن تتكون كلمة المرور من 8 أحرف على الأقل")
        if not re.search(r"[A-Z]", v):
            raise ValueError("يجب أن تحتوي كلمة المرور على حرف كبير واحد على الأقل")
        if not re.search(r"[0-9]", v):
            raise ValueError("يجب أن تحتوي كلمة المرور على رقم واحد على الأقل")
        return v


class MessageResponse(BaseModel):
    message: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class VerifyAccountRequest(BaseModel):
    email: EmailStr
    verification_code: str

