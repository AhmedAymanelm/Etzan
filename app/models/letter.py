import re
from pydantic import BaseModel, Field, field_validator
from typing import Literal


class LetterAnalysisRequest(BaseModel):
    """نموذج طلب تحليل علم الحرف"""
    name: str = Field(..., min_length=1, description="الاسم العربي")
    age: int = Field(..., gt=0, description="العمر (يجب أن يكون أكبر من 0)")
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """التحقق من أن الاسم غير فارغ بعد إزالة المسافات وأن يكون بالعربية"""
        cleaned = v.strip()
        if not cleaned:
            raise ValueError('الاسم لا يمكن أن يكون فارغًا')
        if not re.match(r"^[\u0600-\u06FF\s]+$", cleaned):
            raise ValueError('يجب أن يكون الاسم باللغة العربية فقط')
        return cleaned
    
    @field_validator('age')
    @classmethod
    def validate_age(cls, v: int) -> int:
        """التحقق من أن العمر موجب"""
        if v <= 0:
            raise ValueError('العمر يجب أن يكون أكبر من صفر')
        return v


class LetterAnalysisResponse(BaseModel):
    """نموذج نتيجة تحليل علم الحرف"""
    name: str
    age: int
    letters_count: int
    stage: int
    governing_letter: str
    is_dependent: bool = False
    guidance_type: Literal["spiritual", "behavioral", "physical", "dependent"]
    guidance: str


class GuidanceDictionary(BaseModel):
    """نموذج قاموس التوجيهات"""
    spiritual: dict[str, str]
    behavioral: dict[str, str]
    physical: dict[str, str]


# --- Admin Schemas ---

class LetterGuidanceBase(BaseModel):
    letter: str = Field(..., max_length=10, description="الحرف")
    guidance_type: Literal["spiritual", "behavioral", "physical"] = Field(..., description="نوع التوجيه")
    guidance_text: str = Field(..., description="نص التوجيه")


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
