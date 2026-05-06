from sqlalchemy import Column, Integer, String
from app.database import Base

class LetterGuidance(Base):
    __tablename__ = "letter_guidances"

    id = Column(Integer, primary_key=True, index=True)
    letter = Column(String(10), unique=True, index=True, nullable=False)
    guidance_type = Column(String(50), nullable=False)  # spiritual, behavioral, physical
    guidance_text = Column(String, nullable=False)
