from pydantic import BaseModel, Field, field_validator, model_validator
import re
from typing import Literal, Optional, Dict
from app.utils.date_parser import normalize_date_input


class BirthDataInput(BaseModel):
    """Nested birth data payload used by some clients."""
    year: int = Field(..., ge=1, le=9999)
    month: int = Field(..., ge=1, le=12)
    day: int = Field(..., ge=1, le=31)
    hour: int = Field(default=12, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    second: int = Field(default=0, ge=0, le=59)
    city: str = Field(default="")
    country_code: str = Field(default="")


class AstrologyRequest(BaseModel):
    """Daily horoscope analysis request model"""
    name: str = Field(default="", description="User name (optional)")
    
    # New Top-level date/time fields for easier Flutter integration
    year: Optional[int] = Field(None, ge=1, le=9999)
    month: Optional[int] = Field(None, ge=1, le=12)
    day: Optional[int] = Field(None, ge=1, le=31)
    hour: Optional[int] = Field(None, ge=0, le=23)
    minute: Optional[int] = Field(None, ge=0, le=59)

    birth_data: Optional[BirthDataInput] = Field(
        default=None,
        description="Legacy support for birth_data object"
    )
    birth_date: Optional[str] = Field(default=None, description="Birth date (e.g. 1998-01-15)")
    birth_time: Optional[str] = Field(default=None, description="Birth time HH:MM")
    city_of_birth: str = Field(default="", description="City of birth name")
    latitude: Optional[float] = Field(default=None, description="Latitude (optional)")
    longitude: Optional[float] = Field(default=None, description="Longitude (optional)")
    day_type: Literal["today", "tomorrow", "yesterday"] = Field(
        default="today", 
        description="Day type for analysis"
    )
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if cleaned and not re.match(r"^[\u0600-\u06FF\s]+$", cleaned):
            raise ValueError('يجب أن يكون الاسم باللغة العربية فقط')
        return cleaned

    @model_validator(mode="before")
    @classmethod
    def map_birth_data_to_fields(cls, data):
        if not isinstance(data, dict):
            return data

        # Order of priority: 
        # 1. Top-level year/month/day fields (New Flutter friendly)
        # 2. birth_data object fields (Legacy)
        # 3. birth_date string field (Raw)

        year = data.get("year")
        month = data.get("month")
        day = data.get("day")
        hour = data.get("hour")
        minute = data.get("minute")

        # Fallback to birth_data object if top-level fields are missing
        birth_data = data.get("birth_data")
        if birth_data and isinstance(birth_data, dict):
            year = year or birth_data.get("year")
            month = month or birth_data.get("month")
            day = day or birth_data.get("day")
            hour = hour if hour is not None else birth_data.get("hour", 12)
            minute = minute if minute is not None else birth_data.get("minute", 0)
        
        # Default hour/minute if still None
        if hour is None: hour = 12
        if minute is None: minute = 0

        if data.get("birth_date") in (None, "") and year is not None and month is not None and day is not None:
            data["birth_date"] = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

        if data.get("birth_time") in (None, "") and hour is not None:
            data["birth_time"] = f"{int(hour):02d}:{int(minute):02d}"

        return data

    @field_validator('birth_date')
    @classmethod
    def validate_birth_date(cls, v: Optional[str]) -> str:
        """Validate and normalize birth date to YYYY-MM-DD."""
        if not v:
            raise ValueError('يجب إرسال birth_date أو birth_data')
        try:
            return normalize_date_input(v)
        except ValueError:
            raise ValueError('تاريخ الميلاد يجب أن يكون بصيغة YYYY-MM-DD أو 15-Jan-1998 أو 1992-Sep-05')


class AstrologyResponse(BaseModel):
    """Daily horoscope analysis response model"""
    name: str = Field(default="", description="Name")
    sun_sign: str = Field(..., description="Sun sign")
    moon_sign: str = Field(default="", description="Moon sign")
    ascendant: str = Field(default="", description="Ascendant")
    planets: Dict[str, str] = Field(default_factory=dict, description="Planet positions")
    birth_date: str
    day_type: str
    psychological_state: str = Field(..., description="Psychological state")
    emotional_state: str = Field(..., description="Emotional state")
    mental_state: str = Field(..., description="Mental state")
    physical_state: str = Field(..., description="Physical state")
    luck_level: str = Field(..., description="Luck level")
    lucky_color: str = Field(..., description="Lucky color")
    lucky_number: str = Field(..., description="Lucky number")
    compatibility: str = Field(..., description="Compatibility")
    advice: str = Field(..., description="Advice")
    warning: str = Field(..., description="Warning")
