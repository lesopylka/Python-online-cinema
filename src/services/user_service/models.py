"""
Модели базы данных для User Service.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, Text
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from enum import Enum as PyEnum
import uuid
from src.config.database import Base


class UserRole(PyEnum):
    """Роли пользователей."""
    GUEST = "guest"
    USER = "user"
    SUBSCRIBER = "subscriber"
    MODERATOR = "moderator"
    ADMIN = "admin"


class UserStatus(PyEnum):
    """Статусы пользователей."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BANNED = "banned"


class User(Base):
    """
    Модель пользователя.
    
    Attributes:
        id: UUID пользователя
        email: Email (уникальный)
        username: Имя пользователя (уникальное)
        hashed_password: Хэшированный пароль
        full_name: Полное имя
        phone_number: Номер телефона
        avatar_url: URL аватара
        role: Роль пользователя
        status: Статус пользователя
        email_verified: Подтвержден ли email
        phone_verified: Подтвержден ли телефон
        last_login: Дата последнего входа
        preferences: Настройки пользователя (JSON)
        created_at: Дата создания
        updated_at: Дата обновления
    """
    
    __tablename__ = "users"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    
    full_name = Column(String(255))
    phone_number = Column(String(20))
    avatar_url = Column(String(500))
    
    role = Column(
        Enum(UserRole),
        default=UserRole.USER,
        nullable=False
    )
    status = Column(
        Enum(UserStatus),
        default=UserStatus.ACTIVE,
        nullable=False
    )
    
    email_verified = Column(Boolean, default=False)
    phone_verified = Column(Boolean, default=False)
    
    last_login = Column(DateTime(timezone=True))
    
    preferences = Column(
        JSONB,
        default={
            "language": "ru",
            "theme": "light",
            "notifications": {
                "email": True,
                "push": True,
                "sms": False
            },
            "playback": {
                "quality": "auto",
                "autoplay": True,
                "subtitles": True
            }
        }
    )
    
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now()
    )
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": str(self.id),
            "email": self.email,
            "username": self.username,
            "full_name": self.full_name,
            "phone_number": self.phone_number,
            "avatar_url": self.avatar_url,
            "role": self.role.value,
            "status": self.status.value,
            "email_verified": self.email_verified,
            "phone_verified": self.phone_verified,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "preferences": self.preferences,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class UserSession(Base):
    """
    Модель сессии пользователя.
    
    Attributes:
        id: UUID сессии
        user_id: ID пользователя
        access_token: JWT access токен
        refresh_token: JWT refresh токен
        user_agent: User agent браузера
        ip_address: IP адрес
        expires_at: Время истечения
        created_at: Дата создания
        last_activity: Дата последней активности
    """
    
    __tablename__ = "user_sessions"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    user_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True
    )
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    
    user_agent = Column(Text)
    ip_address = Column(String(45))  # Поддержка IPv6
    
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    last_activity = Column(
        DateTime(timezone=True),
        onupdate=func.now()
    )


class EmailVerification(Base):
    """
    Модель для верификации email.
    
    Attributes:
        id: UUID верификации
        user_id: ID пользователя
        email: Email для верификации
        token: Токен верификации
        expires_at: Время истечения токена
        verified_at: Время верификации
        created_at: Дата создания
    """
    
    __tablename__ = "email_verifications"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    user_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True
    )
    email = Column(String(255), nullable=False)
    token = Column(String(100), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    verified_at = Column(DateTime(timezone=True))
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )


class PasswordReset(Base):
    """
    Модель для сброса пароля.
    
    Attributes:
        id: UUID запроса
        user_id: ID пользователя
        token: Токен сброса
        expires_at: Время истечения токена
        used_at: Время использования
        created_at: Дата создания
    """
    
    __tablename__ = "password_resets"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    user_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True
    )
    token = Column(String(100), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True))
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )


class UserActivity(Base):
    """
    Модель для активности пользователя.
    
    Attributes:
        id: UUID активности
        user_id: ID пользователя
        activity_type: Тип активности
        details: Детали активности (JSON)
        ip_address: IP адрес
        user_agent: User agent
        created_at: Дата создания
    """
    
    __tablename__ = "user_activities"
    
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    user_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True
    )
    activity_type = Column(String(50), nullable=False, index=True)
    details = Column(JSONB)
    ip_address = Column(String(45))
    user_agent = Column(Text)
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )