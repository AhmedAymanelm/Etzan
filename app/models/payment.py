from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy import UUID
from datetime import datetime
import uuid
from app.database import Base

class PaymentRecord(Base):
    __tablename__ = "payment_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Fawaterk transaction tracking
    order_id = Column(String, unique=True, index=True, nullable=False)
    session_id = Column(String, index=True, nullable=True)
    service_type = Column(String, nullable=True) # e.g., "comprehensive_report"
    
    # Financial details
    amount = Column(Float, nullable=False)
    currency = Column(String, default="EGP")
    
    # Status
    status = Column(String, default="PENDING") # PENDING, SUCCESS, FAILED
    payment_method = Column(String, nullable=True) # card, wallet
    
    # Dates
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
