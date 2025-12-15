from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
import jwt
from src.config.settings import settings
from src.shared.exceptions import AuthenticationError, AuthorizationError

security = HTTPBearer(auto_error=False)

async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security)
) -> Dict[str, Any]:
    """
    Dependency для получения текущего пользователя из JWT токена.
    
    Args:
        request: FastAPI Request объект
        credentials: HTTP Bearer токен
        
    Returns:
        Dict с данными пользователя
        
    Raises:
        AuthenticationError: Если токен невалиден или отсутствует
    """
    # Для публичных endpoints пропускаем проверку
    public_paths = [
        "/", "/health", "/docs", "/redoc", "/openapi.json", "/metrics",
        "/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh"
    ]
    
    if request.url.path in public_paths:
        return {"id": None, "email": None, "roles": ["guest"]}
    
    if not credentials:
        raise AuthenticationError("Missing authentication token")
    
    token = credentials.credentials
    
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        
        user_data = {
            "id": payload.get("sub"),
            "email": payload.get("email"),
            "roles": payload.get("roles", []),
            "permissions": payload.get("permissions", [])
        }
        
        # Сохраняем в request state для использования в других частях приложения
        request.state.user = user_data
        
        return user_data
        
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")


def require_role(required_role: str):
    """
    Dependency фабрика для проверки ролей пользователя.
    
    Args:
        required_role: Требуемая роль
        
    Returns:
        Dependency функция
    """
    def role_checker(user: Dict[str, Any] = Depends(get_current_user)):
        if required_role not in user.get("roles", []):
            raise AuthorizationError(
                f"Required role: {required_role}. "
                f"User roles: {user.get('roles', [])}"
            )
        return user
    
    return role_checker


def require_permission(required_permission: str):
    """
    Dependency фабрика для проверки прав пользователя.
    
    Args:
        required_permission: Требуемое право
        
    Returns:
        Dependency функция
    """
    def permission_checker(user: Dict[str, Any] = Depends(get_current_user)):
        if required_permission not in user.get("permissions", []):
            raise AuthorizationError(
                f"Required permission: {required_permission}"
            )
        return user
    
    return permission_checker


def get_pagination_params(
    page: int = 1,
    size: int = 20,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "asc"
) -> Dict[str, Any]:
    """
    Dependency для получения параметров пагинации.
    
    Args:
        page: Номер страницы (начинается с 1)
        size: Количество элементов на странице
        sort_by: Поле для сортировки
        sort_order: Порядок сортировки (asc/desc)
        
    Returns:
        Dict с параметрами пагинации
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