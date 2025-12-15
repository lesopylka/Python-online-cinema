"""
Pydantic схемы для User Service.
"""

from pydantic import BaseModel, Field, EmailStr, validator, root_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import re
from src.shared.schemas import Token as BaseToken


# Enums для схем
class UserRole(str, Enum):
    """Роли пользователей."""
    GUEST = "guest"
    USER = "user"
    SUBSCRIBER = "subscriber"
    MODERATOR = "moderator"
    ADMIN = "admin"


class UserStatus(str, Enum):
    """Статусы пользователей."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BANNED = "banned"


# Базовые схемы
class UserBase(BaseModel):
    """Базовая схема пользователя."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone_number: Optional[str] = None
    avatar_url: Optional[str] = None
    
    @validator('username')
    def validate_username(cls, v):
        """Валидация имени пользователя."""
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError('Username can only contain letters, numbers and underscores')
        return v
    
    @validator('phone_number')
    def validate_phone_number(cls, v):
        """Валидация номера телефона."""
        if v is not None:
            # Простая валидация российских номеров
            if not re.match(r'^\+7\d{10}$', v):
                raise ValueError('Invalid phone number format')
        return v


class UserCreate(UserBase):
    """Схема для создания пользователя."""
    password: str = Field(..., min_length=8, max_length=100)
    password_confirm: str
    
    @root_validator
    def validate_passwords(cls, values):
        """Валидация совпадения паролей."""
        password = values.get('password')
        password_confirm = values.get('password_confirm')
        
        if password != password_confirm:
            raise ValueError('Passwords do not match')
        
        # Проверка сложности пароля
        if not re.search(r'[A-Z]', password):
            raise ValueError('Password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', password):
            raise ValueError('Password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', password):
            raise ValueError('Password must contain at least one digit')
        
        return values


class UserUpdate(BaseModel):
    """Схема для обновления пользователя."""
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone_number: Optional[str] = None
    avatar_url: Optional[str] = None
    preferences: Optional[Dict[str, Any]] = None
    
    @validator('username')
    def validate_username(cls, v):
        if v is not None:
            if not re.match(r'^[a-zA-Z0-9_]+$', v):
                raise ValueError('Username can only contain letters, numbers and underscores')
        return v


class UserLogin(BaseModel):
    """Схема для входа пользователя."""
    email: Optional[EmailStr] = None
    username: Optional[str] = None
    password: str = Field(..., min_length=1)
    
    @validator('password')
    def password_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError('Password cannot be empty')
        return v.strip()


class UserResponse(UserBase):
    """Схема для ответа с данными пользователя."""
    id: str
    role: UserRole
    status: UserStatus
    email_verified: bool
    phone_verified: bool
    last_login: Optional[datetime]
    preferences: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class UserProfileResponse(BaseModel):
    """Схема для публичного профиля пользователя."""
    id: str
    username: str
    full_name: Optional[str]
    avatar_url: Optional[str]
    role: UserRole
    created_at: datetime
    
    class Config:
        from_attributes = True


class Token(BaseToken):
    """Схема токена с дополнительными полями."""
    user: UserResponse


class PasswordChange(BaseModel):
    """Схема для изменения пароля."""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)
    new_password_confirm: str
    
    @root_validator
    def validate_passwords(cls, values):
        current_password = values.get('current_password')
        new_password = values.get('new_password')
        new_password_confirm = values.get('new_password_confirm')
        
        if current_password == new_password:
            raise ValueError('New password must be different from current password')
        
        if new_password != new_password_confirm:
            raise ValueError('New passwords do not match')
        
        # Проверка сложности пароля
        if not re.search(r'[A-Z]', new_password):
            raise ValueError('New password must contain at least one uppercase letter')
        if not re.search(r'[a-z]', new_password):
            raise ValueError('New password must contain at least one lowercase letter')
        if not re.search(r'[0-9]', new_password):
            raise ValueError('New password must contain at least one digit')
        
        return values


class PasswordResetRequest(BaseModel):
    """Схема для запроса сброса пароля."""
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """Схема для подтверждения сброса пароля."""
    token: str
    new_password: str = Field(..., min_length=8, max_length=100)
    new_password_confirm: str
    
    @validator('new_password_confirm')
    def passwords_match(cls, v, values):
        if 'new_password' in values and v != values['new_password']:
            raise ValueError('Passwords do not match')
        return v


class EmailVerificationRequest(BaseModel):
    """Схема для запроса верификации email."""
    email: EmailStr


class EmailVerificationConfirm(BaseModel):
    """Схема для подтверждения верификации email."""
    token: str


class UserPreferencesUpdate(BaseModel):
    """Схема для обновления настроек пользователя."""
    language: Optional[str] = None
    theme: Optional[str] = None
    notifications: Optional[Dict[str, bool]] = None
    playback: Optional[Dict[str, Any]] = None


class UserSearchParams(BaseModel):
    """Схема параметров поиска пользователей."""
    email: Optional[str] = None
    username: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    page: int = 1
    size: int = 20
    sort_by: Optional[str] = None
    sort_order: Optional[str] = "asc"