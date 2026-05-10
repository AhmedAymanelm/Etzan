from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any
import re
from app.utils.date_parser import normalize_date_input


class ComprehensiveAnswers(BaseModel):
    """Complete answers for all assessments"""
    
    name: str = Field(..., description="User name")
    age: Optional[int] = Field(None, description="User age for letter science")

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError('الاسم لا يمكن أن يكون فارغًا')
        if not re.match(r"^[\u0600-\u06FF\s]+$", cleaned):
            raise ValueError('يجب أن يكون الاسم باللغة العربية فقط')
        return cleaned

    @field_validator('birth_date')
    @classmethod
    def validate_birth_date(cls, v: str) -> str:
        try:
            return normalize_date_input(v)
        except ValueError:
            raise ValueError('birth_date must be YYYY-MM-DD or 15-Jan-1998')

    
    psychology_answers: List[int] = Field(..., min_length=1)
    
    neuroscience_answers: List[str] = Field(..., min_length=1)
    
    birth_date: str = Field(..., description="YYYY-MM-DD or 15-Jan-1998")
    day_type: str = Field(default="today", description="today/tomorrow/yesterday")
    birth_time: Optional[str] = Field(None, description="HH:MM format")
    city_of_birth: Optional[str] = Field(None, description="اسم مدينة الميلاد")
    gender: Optional[str] = Field(None, description="male/female")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    
    # Optional: pre-computed letter result from /letter/analyze
    letter_result: Optional[Dict[str, Any]] = Field(None, description="Pre-computed letter science result")


class ComprehensiveResultsInput(BaseModel):
    """Input model for submitting pre-computed results from individual assessments"""
    
    name: str = Field(..., description="User name")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError('الاسم لا يمكن أن يكون فارغًا')
        if not re.match(r"^[\u0600-\u06FF\s]+$", cleaned):
            raise ValueError('يجب أن يكون الاسم باللغة العربية فقط')
        return cleaned

    psychology_result: Dict[str, Any] = Field(
        ..., 
        description="Psychology assessment result containing score, level, message, supportive_messages"
    )
    
    neuroscience_result: Dict[str, Any] = Field(
        ..., 
        description="Neuroscience assessment result containing dominant, secondary, description, scores"
    )
    
    astrology_result: Dict[str, Any] = Field(
        ..., 
        description="Astrology analysis result containing sun_sign, ascendant, psychological_state, etc."
    )
    
    letter_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Letter science result containing governing_letter, guidance_type, guidance (optional)"
    )


class ComprehensiveResult(BaseModel):
    """Complete assessment results"""
    
    psychology: dict
    neuroscience: dict
    astrology: dict
    status: str
    message: str
