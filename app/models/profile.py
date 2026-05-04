from pydantic import BaseModel, HttpUrl, Field
from typing import Optional
from datetime import date, time
from pydantic import field_validator
from app.utils.date_parser import parse_date_input

class ProfilePictureUpdateRequest(BaseModel):
    profile_picture_url: str = Field(..., description="رابط صورة الملف الشخصي")

class NameUpdateRequest(BaseModel):
    fullname: str = Field(..., description="الاسم الكامل للمستخدم")

class BirthDetailsUpdateRequest(BaseModel):
    date_of_birth: date = Field(..., description="تاريخ الميلاد")
    city_of_birth: str = Field(..., description="اسم مدينة الميلاد")
    time_of_birth: Optional[time] = Field(None, description="وقت الميلاد")

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def normalize_date_of_birth(cls, v):
        return parse_date_input(v)

class ProfileResponse(BaseModel):
    id: str
    email: str
    fullname: str
    date_of_birth: date
    city_of_birth: str
    time_of_birth: Optional[time]
    profile_picture_url: Optional[str]

    class Config:
        from_attributes = True
