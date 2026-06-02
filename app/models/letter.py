import re
from pydantic import BaseModel, Field, field_validator
from typing import Literal


class LetterAnalysisRequest(BaseModel):
    """Letter science analysis request model"""
    name: str = Field(..., min_length=1, description="Arabic name")
    age: int = Field(..., gt=0, description="Age (must be greater than 0)")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate that the name is not empty after stripping and is in Arabic"""
        cleaned = v.strip()
        if not cleaned:
            raise ValueError('الاسم لا يمكن أن يكون فارغًا')
        if not re.match(r"^[\u0600-\u06FF\s]+$", cleaned):
            raise ValueError('يجب أن يكون الاسم باللغة العربية فقط')
        return cleaned
    
    @field_validator('age')
    @classmethod
    def validate_age(cls, v: int) -> int:
        """Validate that the age is positive"""
        if v <= 0:
            raise ValueError('العمر يجب أن يكون أكبر من صفر')
        return v


class LetterAnalysisResponse(BaseModel):
    """Letter science analysis response model"""
    name: str
    age: int
    letters_count: int
    stage: int
    governing_letter: str
    is_dependent: bool = False
    guidance_type: Literal["spiritual", "behavioral", "physical", "dependent"]
    guidance: str


class GuidanceDictionary(BaseModel):
    """Guidance dictionary model"""
    spiritual: dict[str, str]
    behavioral: dict[str, str]
    physical: dict[str, str]


# --- Admin Schemas ---

class LetterGuidanceBase(BaseModel):
    letter: str = Field(..., max_length=10, description="Letter")
    guidance_type: Literal["spiritual", "behavioral", "physical"] = Field(..., description="Guidance type")
    guidance_text: str = Field(..., description="Guidance text")


class LetterGuidanceCreate(LetterGuidanceBase):
    pass


class LetterGuidanceUpdate(BaseModel):
    letter: str | None = Field(None, max_length=10)
    guidance_type: Literal["spiritual", "behavioral", "physical"] | None = None
    guidance_text: str | None = None


class LetterGuidanceResponse(LetterGuidanceBase):
    id: int

    class Config:
        from_attributes = True
