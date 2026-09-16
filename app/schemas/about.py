from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime

class AboutSectionBase(BaseModel):
    title: str
    content: str
    order: Optional[int] = 0

class AboutSectionCreate(AboutSectionBase):
    pass

class AboutSectionUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    order: Optional[int] = None

class AboutSectionResponse(AboutSectionBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
