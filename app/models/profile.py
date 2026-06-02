from pydantic import BaseModel, HttpUrl, Field
from typing import Optional
from datetime import date, time
from pydantic import field_validator
from app.utils.date_parser import parse_date_input

class ProfilePictureUpdateRequest(BaseModel):
    profile_picture_url: str = Field(..., description="Profile picture URL")

class NameUpdateRequest(BaseModel):
    fullname: str = Field(..., description="Full name")

class BirthDetailsUpdateRequest(BaseModel):
    date_of_birth: date = Field(..., description="Date of birth")
    city_of_birth: str = Field(..., description="City of birth")
    time_of_birth: Optional[time] = Field(None, description="Time of birth")

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def normalize_date_of_birth(cls, v):
        return parse_date_input(v)

class ProfileUpdateRequest(BaseModel):
    """Profile update request - all fields are optional"""
    profile_picture_url: Optional[str] = Field(None, description="Profile picture URL")
    fullname: Optional[str] = Field(None, description="Full name")
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    city_of_birth: Optional[str] = Field(None, description="City of birth")
    time_of_birth: Optional[time] = Field(None, description="Time of birth")

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def normalize_date_of_birth(cls, v):
        if v is None:
            return v
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
