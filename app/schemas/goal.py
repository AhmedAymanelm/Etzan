from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, date
from uuid import UUID

# ── Daily Goal Schemas ──────────────────────────────────────────────

class GoalCreate(BaseModel):
    title: str
    content: str
    target_date: Optional[date] = None # Defaults to today on the server if not provided

class GoalUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    is_completed: Optional[bool] = None

class GoalResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    content: str
    is_completed: bool
    target_date: date
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# ── User Note Schemas ───────────────────────────────────────────────

class NoteCreate(BaseModel):
    content: str

class NoteUpdate(BaseModel):
    content: str

class NoteResponse(BaseModel):
    id: UUID
    user_id: UUID
    content: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
