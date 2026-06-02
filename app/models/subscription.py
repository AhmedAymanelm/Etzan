import uuid
from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy import UUID

from app.database import Base


class UserSubscription(Base):
    """
    Tracks monthly subscriptions for users.
    Created automatically when a payment is confirmed (via webhook or verify).
    Can also be created manually by an admin.
    """
    __tablename__ = "user_subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Linked payment — nullable because admin can grant free subscriptions
    payment_record_id = Column(UUID(as_uuid=True), ForeignKey("payment_records.id", ondelete="SET NULL"), nullable=True)

    # Subscription period
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)

    # State
    is_active = Column(Boolean, default=True, nullable=False)
    plan_type = Column(String, default="monthly", nullable=False)  # "monthly" | "admin_grant"
    granted_by_admin = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<UserSubscription user={self.user_id} expires={self.expires_at}>"
