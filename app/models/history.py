import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class AssessmentHistory(Base):
    __tablename__ = "assessment_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assessment_type = Column(String(50), nullable=False, index=True) # psychology, neuroscience, letter, astrology, comprehensive
    input_data = Column(JSON, nullable=True)
    result_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Note: A relationship back to 'User' model is typically defined on the User model
    # user = relationship("User", back_populates="assessments")

    def __repr__(self):
        return f"<AssessmentHistory {self.assessment_type} run by User {self.user_id}>"
