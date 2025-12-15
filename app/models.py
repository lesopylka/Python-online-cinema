# app/models.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Float, BigInteger, Boolean, ForeignKey, \
    Index  # Добавьте Index здесь
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime

Base = declarative_base()


class UserActivity(Base):
    __tablename__ = "user_activity"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), index=True, nullable=True)
    session_id = Column(String(255), index=True, nullable=False)
    device_id = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 support
    user_agent = Column(Text, nullable=True)

    # Event data
    event_type = Column(String(50), index=True, nullable=False)
    event_name = Column(String(255), nullable=False)
    page_url = Column(Text, nullable=True)
    referrer_url = Column(Text, nullable=True)
    content_id = Column(String(255), index=True, nullable=True)
    content_type = Column(String(50), nullable=True)

    # Metadata
    metadata = Column(JSON, nullable=False, default=dict)

    # Timestamps
    event_timestamp = Column(DateTime, index=True, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    # Analytics
    duration = Column(Float, nullable=True)
    value = Column(Float, nullable=True)

    # Indexes
    __table_args__ = (
        Index('idx_user_timestamp', 'user_id', 'event_timestamp'),
        Index('idx_content_timestamp', 'content_id', 'event_timestamp'),
        Index('idx_session_timestamp', 'session_id', 'event_timestamp'),
    )