import uuid
from datetime import datetime

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class UserDeviceToken(Base):
    """
    Stores FCM device tokens for push notifications.
    Each user can have multiple devices (phone, tablet, etc.).
    """
    __tablename__ = "user_device_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    fcm_token = Column(String, unique=True, nullable=False, index=True)
    device_type = Column(String, nullable=True)    # "android" | "ios"
    device_name = Column(String, nullable=True)    # e.g. "iPhone 15 Pro"

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<UserDeviceToken user={self.user_id} device={self.device_type}>"
