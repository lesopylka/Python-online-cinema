"""
Dependencies для Catalog Service.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID
from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt

from src.config.database import get_db
from src.config.settings import settings
from src.shared.exceptions import AuthenticationError, AuthorizationError
from src.services.user_service import schemas as user_schemas

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


def get_current_user(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Dict[str, Any]:
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
        
        # Возвращаем данные пользователя
        return {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role", user_schemas.UserRole.USER.value),
            "permissions": payload.get("permissions", [])
        }
        
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except (jwt.InvalidTokenError, ValueError) as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")


def get_current_user_optional(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Optional[Dict[str, Any]]:
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
        
        return {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role", user_schemas.UserRole.USER.value),
            "permissions": payload.get("permissions", [])
        }
        
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError):
        return None


def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Dependency для проверки прав администратора.
    
    Raises:
        AuthorizationError: Если пользователь не администратор
    """
    if current_user.get("role") != user_schemas.UserRole.ADMIN.value:
        raise AuthorizationError("Admin rights required")
    return current_user


def require_moderator_or_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Dependency для проверки прав модератора или администратора.
    """
    allowed_roles = [
        user_schemas.UserRole.MODERATOR.value,
        user_schemas.UserRole.ADMIN.value
    ]
    
    if current_user.get("role") not in allowed_roles:
        raise AuthorizationError("Moderator or admin rights required")
    return current_user


def get_pagination_params(
    page: int = 1,
    size: int = 20,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "asc"
) -> Dict[str, Any]:
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


# Быстрые зависимости для часто используемых ролей
def require_user(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Dependency для проверки что пользователь аутентифицирован.
    """
    return current_user