"""
Dependencies для User Service.
"""

import logging
from typing import Optional, Generator
from uuid import UUID
from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt

from src.config.database import get_db
from src.config.settings import settings
from src.shared.exceptions import AuthenticationError, AuthorizationError
from . import crud, models, schemas

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


def get_current_user(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> models.User:
    """
    Dependency для получения текущего пользователя.
    
    Raises:
        AuthenticationError: Если пользователь не аутентифицирован
    """
    if not credentials:
        raise AuthenticationError("Missing authentication token")
    
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type")
        
        user_id = UUID(payload.get("sub"))
        user = crud.get_user(db, user_id)
        
        if not user:
            raise AuthenticationError("User not found")
        
        if user.status != models.UserStatus.ACTIVE:
            raise AuthenticationError(f"User account is {user.status.value}")
        
        return user
        
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except (jwt.InvalidTokenError, ValueError) as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")


def get_current_user_optional(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Optional[models.User]:
    """
    Dependency для получения текущего пользователя (опционально).
    Возвращает None если пользователь не аутентифицирован.
    """
    if not credentials:
        return None
    
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        if payload.get("type") != "access":
            return None
        
        user_id = UUID(payload.get("sub"))
        user = crud.get_user(db, user_id)
        
        if not user or user.status != models.UserStatus.ACTIVE:
            return None
        
        return user
        
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError):
        return None


def require_role(required_role: schemas.UserRole):
    """
    Dependency фабрика для проверки роли пользователя.
    
    Args:
        required_role: Требуемая роль
        
    Returns:
        Dependency функция
    """
    def role_checker(current_user: models.User = Depends(get_current_user)):
        user_role = current_user.role
        
        # Проверяем иерархию ролей
        role_hierarchy = {
            schemas.UserRole.GUEST: 0,
            schemas.UserRole.USER: 1,
            schemas.UserRole.SUBSCRIBER: 2,
            schemas.UserRole.MODERATOR: 3,
            schemas.UserRole.ADMIN: 4
        }
        
        user_level = role_hierarchy.get(user_role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        
        if user_level < required_level:
            raise AuthorizationError(
                f"Required role: {required_role.value}. "
                f"User role: {user_role.value}"
            )
        
        return current_user
    
    return role_checker


def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    """
    Dependency для проверки прав администратора.
    
    Raises:
        AuthorizationError: Если пользователь не администратор
    """
    if current_user.role != models.UserRole.ADMIN:
        raise AuthorizationError("Admin rights required")
    return current_user


def require_moderator_or_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    """
    Dependency для проверки прав модератора или администратора.
    """
    allowed_roles = [models.UserRole.MODERATOR, models.UserRole.ADMIN]
    if current_user.role not in allowed_roles:
        raise AuthorizationError("Moderator or admin rights required")
    return current_user


def get_client_info(request: Request) -> dict:
    """
    Dependency для получения информации о клиенте.
    
    Returns:
        Dict с информацией о клиенте
    """
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "origin": request.headers.get("origin")
    }


def get_pagination_params(
    page: int = 1,
    size: int = 20,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "asc"
) -> dict:
    """
    Dependency для получения параметров пагинации.
    """
    # Валидация параметров
    if page < 1:
        page = 1
    if size < 1:
        size = 1
    if size > 100:
        size = 100
    if sort_order not in ["asc", "desc"]:
        sort_order = "asc"
    
    skip = (page - 1) * size
    
    return {
        "page": page,
        "size": size,
        "skip": skip,
        "sort_by": sort_by,
        "sort_order": sort_order
    }


def get_user_filters(
    email: Optional[str] = None,
    username: Optional[str] = None,
    role: Optional[schemas.UserRole] = None,
    status: Optional[schemas.UserStatus] = None
) -> dict:
    """
    Dependency для получения фильтров пользователей.
    """
    filters = {}
    
    if email:
        filters["email"] = email
    if username:
        filters["username"] = username
    if role:
        filters["role"] = role
    if status:
        filters["status"] = status
    
    return filters


# Быстрые зависимости для часто используемых ролей
require_user = require_role(schemas.UserRole.USER)
require_subscriber = require_role(schemas.UserRole.SUBSCRIBER)
require_moderator = require_role(schemas.UserRole.MODERATOR)