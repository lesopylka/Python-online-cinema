"""
CRUD операции для User Service.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, desc
import jwt
from passlib.context import CryptContext

from . import models, schemas
from src.config.settings import settings
from src.shared.exceptions import (
    NotFoundError, ConflictError, AuthenticationError,
    ValidationError, AuthorizationError
)
from src.shared.kafka_producer import send_kafka_message
from src.monitoring.metrics import (
    record_database_query, record_user_event
)

logger = logging.getLogger(__name__)

# Контекст для хэширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ====== Вспомогательные функции ======

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверка пароля."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Хэширование пароля."""
    return pwd_context.hash(password)


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Создание JWT access токена."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: Dict[str, Any]) -> str:
    """Создание JWT refresh токена."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Dict[str, Any]:
    """Верификация JWT токена."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")


def _record_user_activity(
    db: Session,
    user_id: UUID,
    activity_type: str,
    details: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
):
    """Запись активности пользователя."""
    try:
        activity = models.UserActivity(
            user_id=user_id,
            activity_type=activity_type,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
        db.add(activity)
        db.commit()
        
        # Отправляем событие в Kafka
        send_kafka_message(
            topic=settings.KAFKA_TOPIC_USER_ACTIVITY,
            value={
                "user_id": str(user_id),
                "activity_type": activity_type,
                "timestamp": datetime.utcnow().isoformat(),
                "details": details or {}
            }
        )
        
        # Записываем метрику
        record_user_event(activity_type, "user")
        
    except Exception as e:
        logger.error(f"Failed to record user activity: {e}")
        db.rollback()


# ====== CRUD операции для пользователей ======

def get_user(db: Session, user_id: UUID) -> Optional[models.User]:
    """Получение пользователя по ID."""
    start_time = datetime.now()
    
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "users", duration, user is not None)
        
        return user
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "users", duration, False)
        raise


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    """Получение пользователя по email."""
    start_time = datetime.now()
    
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "users", duration, user is not None)
        
        return user
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "users", duration, False)
        raise


def get_user_by_username(db: Session, username: str) -> Optional[models.User]:
    """Получение пользователя по username."""
    start_time = datetime.now()
    
    try:
        user = db.query(models.User).filter(models.User.username == username).first()
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "users", duration, user is not None)
        
        return user
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "users", duration, False)
        raise


def get_users(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    filters: Optional[Dict[str, Any]] = None
) -> List[models.User]:
    """Получение списка пользователей с фильтрацией."""
    start_time = datetime.now()
    
    try:
        query = db.query(models.User)
        
        if filters:
            if "email" in filters:
                query = query.filter(models.User.email.ilike(f"%{filters['email']}%"))
            if "username" in filters:
                query = query.filter(models.User.username.ilike(f"%{filters['username']}%"))
            if "role" in filters:
                query = query.filter(models.User.role == filters["role"])
            if "status" in filters:
                query = query.filter(models.User.status == filters["status"])
        
        users = query.order_by(models.User.created_at.desc()).offset(skip).limit(limit).all()
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "users", duration, True)
        
        return users
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "users", duration, False)
        raise


def count_users(db: Session, filters: Optional[Dict[str, Any]] = None) -> int:
    """Подсчет количества пользователей."""
    start_time = datetime.now()
    
    try:
        query = db.query(models.User)
        
        if filters:
            if "role" in filters:
                query = query.filter(models.User.role == filters["role"])
            if "status" in filters:
                query = query.filter(models.User.status == filters["status"])
        
        count = query.count()
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("count", "users", duration, True)
        
        return count
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("count", "users", duration, False)
        raise


def create_user(db: Session, user: schemas.UserCreate, ip_address: Optional[str] = None) -> models.User:
    """Создание нового пользователя."""
    start_time = datetime.now()
    
    try:
        # Проверка существования пользователя
        db_user_email = get_user_by_email(db, email=user.email)
        if db_user_email:
            raise ConflictError(f"User with email {user.email} already exists")
        
        db_user_username = get_user_by_username(db, username=user.username)
        if db_user_username:
            raise ConflictError(f"User with username {user.username} already exists")
        
        # Создание пользователя
        hashed_password = get_password_hash(user.password)
        
        db_user = models.User(
            email=user.email,
            username=user.username,
            hashed_password=hashed_password,
            full_name=user.full_name,
            phone_number=user.phone_number,
            avatar_url=user.avatar_url
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        # Запись активности
        _record_user_activity(
            db=db,
            user_id=db_user.id,
            activity_type="registration",
            details={"method": "email"},
            ip_address=ip_address
        )
        
        # Отправка события в Kafka
        send_kafka_message(
            topic=settings.KAFKA_TOPIC_NOTIFICATIONS,
            value={
                "type": "user_registered",
                "user_id": str(db_user.id),
                "email": db_user.email,
                "username": db_user.username,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "users", duration, True)
        
        logger.info(f"User created: {db_user.email} ({db_user.id})")
        return db_user
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "users", duration, False)
        raise


def update_user(
    db: Session,
    user_id: UUID,
    user_update: schemas.UserUpdate,
    current_user_id: UUID
) -> models.User:
    """Обновление пользователя."""
    start_time = datetime.now()
    
    try:
        db_user = get_user(db, user_id)
        if not db_user:
            raise NotFoundError("user", user_id)
        
        # Проверка прав доступа
        if db_user.id != current_user_id:
            # Проверяем, является ли current_user администратором
            current_user = get_user(db, current_user_id)
            if not current_user or current_user.role != models.UserRole.ADMIN:
                raise AuthorizationError("Cannot update other users")
        
        # Проверка уникальности email
        if user_update.email and user_update.email != db_user.email:
            existing_user = get_user_by_email(db, user_update.email)
            if existing_user and existing_user.id != user_id:
                raise ConflictError(f"Email {user_update.email} already in use")
        
        # Проверка уникальности username
        if user_update.username and user_update.username != db_user.username:
            existing_user = get_user_by_username(db, user_update.username)
            if existing_user and existing_user.id != user_id:
                raise ConflictError(f"Username {user_update.username} already in use")
        
        # Обновление полей
        update_data = user_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(db_user, field, value)
        
        db.commit()
        db.refresh(db_user)
        
        # Запись активности
        _record_user_activity(
            db=db,
            user_id=db_user.id,
            activity_type="profile_updated",
            details={"updated_fields": list(update_data.keys())}
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "users", duration, True)
        
        logger.info(f"User updated: {db_user.id}")
        return db_user
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "users", duration, False)
        raise


def delete_user(db: Session, user_id: UUID, current_user_id: UUID) -> bool:
    """Удаление пользователя."""
    start_time = datetime.now()
    
    try:
        db_user = get_user(db, user_id)
        if not db_user:
            raise NotFoundError("user", user_id)
        
        # Проверка прав доступа
        if db_user.id != current_user_id:
            current_user = get_user(db, current_user_id)
            if not current_user or current_user.role != models.UserRole.ADMIN:
                raise AuthorizationError("Cannot delete other users")
        
        # Нельзя удалить администратора
        if db_user.role == models.UserRole.ADMIN:
            raise AuthorizationError("Cannot delete admin user")
        
        db.delete(db_user)
        db.commit()
        
        # Запись активности
        _record_user_activity(
            db=db,
            user_id=db_user.id,
            activity_type="account_deleted",
            details={"deleted_by": str(current_user_id)}
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("delete", "users", duration, True)
        
        logger.info(f"User deleted: {user_id}")
        return True
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("delete", "users", duration, False)
        raise


def change_password(
    db: Session,
    user_id: UUID,
    password_change: schemas.PasswordChange
) -> bool:
    """Изменение пароля пользователя."""
    start_time = datetime.now()
    
    try:
        db_user = get_user(db, user_id)
        if not db_user:
            raise NotFoundError("user", user_id)
        
        # Проверка текущего пароля
        if not verify_password(password_change.current_password, db_user.hashed_password):
            raise AuthenticationError("Current password is incorrect")
        
        # Обновление пароля
        db_user.hashed_password = get_password_hash(password_change.new_password)
        db.commit()
        
        # Запись активности
        _record_user_activity(
            db=db,
            user_id=db_user.id,
            activity_type="password_changed"
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "users", duration, True)
        
        logger.info(f"Password changed for user: {user_id}")
        return True
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "users", duration, False)
        raise


# ====== Аутентификация и авторизация ======

def authenticate_user(
    db: Session,
    login_data: schemas.UserLogin,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Optional[models.User]:
    """Аутентификация пользователя."""
    start_time = datetime.now()
    
    try:
        # Поиск пользователя по email или username
        db_user = None
        if login_data.email:
            db_user = get_user_by_email(db, email=login_data.email)
        elif login_data.username:
            db_user = get_user_by_username(db, username=login_data.username)
        
        if not db_user:
            raise AuthenticationError("Invalid credentials")
        
        # Проверка статуса пользователя
        if db_user.status != models.UserStatus.ACTIVE:
            if db_user.status == models.UserStatus.SUSPENDED:
                raise AuthenticationError("Account is suspended")
            elif db_user.status == models.UserStatus.BANNED:
                raise AuthenticationError("Account is banned")
            else:
                raise AuthenticationError("Account is not active")
        
        # Проверка пароля
        if not verify_password(login_data.password, db_user.hashed_password):
            raise AuthenticationError("Invalid credentials")
        
        # Обновление времени последнего входа
        db_user.last_login = datetime.utcnow()
        db.commit()
        db.refresh(db_user)
        
        # Запись активности
        _record_user_activity(
            db=db,
            user_id=db_user.id,
            activity_type="login",
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "users", duration, True)
        
        return db_user
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "users", duration, False)
        raise


def create_user_session(
    db: Session,
    user_id: UUID,
    access_token: str,
    refresh_token: str,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None
) -> models.UserSession:
    """Создание сессии пользователя."""
    start_time = datetime.now()
    
    try:
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        session = models.UserSession(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=expires_at
        )
        
        db.add(session)
        db.commit()
        db.refresh(session)
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "user_sessions", duration, True)
        
        return session
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "user_sessions", duration, False)
        raise


def refresh_access_token(
    db: Session,
    refresh_token: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Dict[str, str]:
    """Обновление access токена."""
    start_time = datetime.now()
    
    try:
        # Проверка токена
        payload = verify_token(refresh_token)
        
        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type")
        
        user_id = UUID(payload.get("sub"))
        db_user = get_user(db, user_id)
        
        if not db_user:
            raise AuthenticationError("User not found")
        
        # Поиск сессии
        session = db.query(models.UserSession).filter(
            models.UserSession.refresh_token == refresh_token,
            models.UserSession.expires_at > datetime.utcnow()
        ).first()
        
        if not session:
            raise AuthenticationError("Invalid or expired refresh token")
        
        # Создание новых токенов
        access_token = create_access_token({
            "sub": str(db_user.id),
            "email": db_user.email,
            "role": db_user.role.value,
            "permissions": []
        })
        
        # Обновление времени последней активности
        session.last_activity = datetime.utcnow()
        db.commit()
        
        # Запись активности
        _record_user_activity(
            db=db,
            user_id=db_user.id,
            activity_type="token_refreshed",
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "user_sessions", duration, True)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "user_sessions", duration, False)
        raise


def logout_user(db: Session, user_id: UUID, token: Optional[str] = None) -> bool:
    """Выход пользователя из системы."""
    start_time = datetime.now()
    
    try:
        if token:
            # Удаление конкретной сессии
            session = db.query(models.UserSession).filter(
                models.UserSession.access_token == token,
                models.UserSession.user_id == user_id
            ).first()
            
            if session:
                db.delete(session)
        else:
            # Удаление всех сессий пользователя
            sessions = db.query(models.UserSession).filter(
                models.UserSession.user_id == user_id
            ).all()
            
            for session in sessions:
                db.delete(session)
        
        db.commit()
        
        # Запись активности
        _record_user_activity(
            db=db,
            user_id=user_id,
            activity_type="logout"
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("delete", "user_sessions", duration, True)
        
        logger.info(f"User logged out: {user_id}")
        return True
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("delete", "user_sessions", duration, False)
        raise


# ====== Верификация email ======

def create_email_verification(db: Session, user_id: UUID, email: str) -> models.EmailVerification:
    """Создание токена верификации email."""
    start_time = datetime.now()
    
    try:
        # Удаляем старые токены
        db.query(models.EmailVerification).filter(
            models.EmailVerification.user_id == user_id,
            models.EmailVerification.verified_at.is_(None)
        ).delete()
        
        # Создаем новый токен
        token = str(uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        verification = models.EmailVerification(
            user_id=user_id,
            email=email,
            token=token,
            expires_at=expires_at
        )
        
        db.add(verification)
        db.commit()
        db.refresh(verification)
        
        # Отправка события в Kafka для уведомления
        send_kafka_message(
            topic=settings.KAFKA_TOPIC_NOTIFICATIONS,
            value={
                "type": "email_verification_requested",
                "user_id": str(user_id),
                "email": email,
                "token": token,
                "expires_at": expires_at.isoformat()
            }
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "email_verifications", duration, True)
        
        return verification
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "email_verifications", duration, False)
        raise


def verify_email(db: Session, token: str) -> bool:
    """Верификация email по токену."""
    start_time = datetime.now()
    
    try:
        verification = db.query(models.EmailVerification).filter(
            models.EmailVerification.token == token,
            models.EmailVerification.expires_at > datetime.utcnow(),
            models.EmailVerification.verified_at.is_(None)
        ).first()
        
        if not verification:
            raise ValidationError("Invalid or expired verification token")
        
        # Находим пользователя
        user = get_user(db, verification.user_id)
        if not user:
            raise NotFoundError("user", verification.user_id)
        
        # Обновляем статус верификации
        user.email_verified = True
        verification.verified_at = datetime.utcnow()
        
        db.commit()
        
        # Запись активности
        _record_user_activity(
            db=db,
            user_id=user.id,
            activity_type="email_verified"
        )
        
        # Отправка события в Kafka
        send_kafka_message(
            topic=settings.KAFKA_TOPIC_NOTIFICATIONS,
            value={
                "type": "email_verified",
                "user_id": str(user.id),
                "email": user.email,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "email_verifications", duration, True)
        
        logger.info(f"Email verified for user: {user.id}")
        return True
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "email_verifications", duration, False)
        raise


# ====== Сброс пароля ======

def create_password_reset(db: Session, email: str) -> Optional[models.PasswordReset]:
    """Создание токена для сброса пароля."""
    start_time = datetime.now()
    
    try:
        user = get_user_by_email(db, email)
        if not user:
            # Не раскрываем, что пользователь не найден
            return None
        
        # Удаляем старые токены
        db.query(models.PasswordReset).filter(
            models.PasswordReset.user_id == user.id,
            models.PasswordReset.used_at.is_(None)
        ).delete()
        
        # Создаем новый токен
        token = str(uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=1)
        
        reset = models.PasswordReset(
            user_id=user.id,
            token=token,
            expires_at=expires_at
        )
        
        db.add(reset)
        db.commit()
        db.refresh(reset)
        
        # Отправка события в Kafka для уведомления
        send_kafka_message(
            topic=settings.KAFKA_TOPIC_NOTIFICATIONS,
            value={
                "type": "password_reset_requested",
                "user_id": str(user.id),
                "email": user.email,
                "token": token,
                "expires_at": expires_at.isoformat()
            }
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "password_resets", duration, True)
        
        return reset
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "password_resets", duration, False)
        raise


def reset_password(db: Session, token: str, new_password: str) -> bool:
    """Сброс пароля по токену."""
    start_time = datetime.now()
    
    try:
        reset = db.query(models.PasswordReset).filter(
            models.PasswordReset.token == token,
            models.PasswordReset.expires_at > datetime.utcnow(),
            models.PasswordReset.used_at.is_(None)
        ).first()
        
        if not reset:
            raise ValidationError("Invalid or expired reset token")
        
        # Находим пользователя
        user = get_user(db, reset.user_id)
        if not user:
            raise NotFoundError("user", reset.user_id)
        
        # Обновляем пароль
        user.hashed_password = get_password_hash(new_password)
        reset.used_at = datetime.utcnow()
        
        db.commit()
        
        # Запись активности
        _record_user_activity(
            db=db,
            user_id=user.id,
            activity_type="password_reset"
        )
        
        # Отправка события в Kafka
        send_kafka_message(
            topic=settings.KAFKA_TOPIC_NOTIFICATIONS,
            value={
                "type": "password_reset_completed",
                "user_id": str(user.id),
                "email": user.email,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        # Удаляем все сессии пользователя
        logout_user(db, user.id)
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "password_resets", duration, True)
        
        logger.info(f"Password reset for user: {user.id}")
        return True
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "password_resets", duration, False)
        raise


# ====== Управление ролями и статусами ======

def update_user_role(
    db: Session,
    user_id: UUID,
    new_role: schemas.UserRole,
    admin_user_id: UUID
) -> models.User:
    """Обновление роли пользователя (только для администраторов)."""
    start_time = datetime.now()
    
    try:
        # Проверка прав администратора
        admin_user = get_user(db, admin_user_id)
        if not admin_user or admin_user.role != models.UserRole.ADMIN:
            raise AuthorizationError("Admin rights required")
        
        db_user = get_user(db, user_id)
        if not db_user:
            raise NotFoundError("user", user_id)
        
        # Нельзя изменить роль администратора
        if db_user.role == models.UserRole.ADMIN:
            raise AuthorizationError("Cannot change admin role")
        
        old_role = db_user.role
        db_user.role = models.UserRole(new_role)
        
        db.commit()
        db.refresh(db_user)
        
        # Запись активности
        _record_user_activity(
            db=db,
            user_id=db_user.id,
            activity_type="role_updated",
            details={"old_role": old_role.value, "new_role": new_role.value}
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "users", duration, True)
        
        logger.info(f"User role updated: {user_id} from {old_role} to {new_role}")
        return db_user
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "users", duration, False)
        raise


def update_user_status(
    db: Session,
    user_id: UUID,
    new_status: schemas.UserStatus,
    admin_user_id: UUID
) -> models.User:
    """Обновление статуса пользователя (только для администраторов)."""
    start_time = datetime.now()
    
    try:
        # Проверка прав администратора
        admin_user = get_user(db, admin_user_id)
        if not admin_user or admin_user.role != models.UserRole.ADMIN:
            raise AuthorizationError("Admin rights required")
        
        db_user = get_user(db, user_id)
        if not db_user:
            raise NotFoundError("user", user_id)
        
        old_status = db_user.status
        db_user.status = models.UserStatus(new_status)
        
        db.commit()
        db.refresh(db_user)
        
        # Запись активности
        _record_user_activity(
            db=db,
            user_id=db_user.id,
            activity_type="status_updated",
            details={"old_status": old_status.value, "new_status": new_status.value}
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "users", duration, True)
        
        logger.info(f"User status updated: {user_id} from {old_status} to {new_status}")
        return db_user
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "users", duration, False)
        raise