import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON

from app.database import Base


class NotificationLog(Base):
    """
    Logs every push notification sent from the admin dashboard.
    Tracks target type, recipient info, and delivery stats.
    """
    __tablename__ = "notification_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)

    # "broadcast" | "user" | "group"
    target_type = Column(String, nullable=False, default="broadcast")

    # For targeted / group notifications — list of user UUIDs
    target_user_ids = Column(JSON, nullable=True)

    # Delivery stats
    sent_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)

    # Extra data payload (e.g. deeplink, screen route)
    data_payload = Column(JSON, nullable=True)

    # Admin who sent the notification
    sent_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<NotificationLog title='{self.title}' target={self.target_type} sent={self.sent_count}>"
