import uuid
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON, Date, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import String as SAString
from datetime import datetime
from app.database import Base


class DailyCheckInQuestion(Base):
    """Questions for the daily check-in survey"""
    __tablename__ = "daily_checkin_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(Text, nullable=False)           # Question text (Arabic)
    options = Column(JSON, nullable=False)        # List of 3 option strings
    order_index = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "text": self.text,
            "options": self.options if isinstance(self.options, list) else [],
            "order_index": self.order_index,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DailyCheckInResponse(Base):
    """Daily check-in submission by a user"""
    __tablename__ = "daily_checkin_responses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(SAString(36), nullable=False, index=True)   # UUID as string
    date = Column(Date, nullable=False, index=True)              # Date of submission
    answers = Column(JSON, nullable=False)                       # {question_id: selected_option_index}
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date.isoformat() if self.date else None,
            "answers": self.answers,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
