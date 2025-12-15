"""
Кастомные исключения для онлайн-кинотеатра.
Все исключения наследуются от ServiceException.
"""

from typing import Optional, Dict, Any, List
from fastapi import status


class ServiceException(Exception):
    """
    Базовое исключение для всех сервисов.
    
    Attributes:
        message: Сообщение об ошибке
        code: Уникальный код ошибки
        status_code: HTTP статус код
        details: Дополнительные детали ошибки
    """
    
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code or "INTERNAL_ERROR"
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование исключения в словарь."""
        return {
            "detail": self.message,
            "code": self.code,
            "status_code": self.status_code,
            **self.details
        }


class ValidationError(ServiceException):
    """Ошибка валидации данных."""
    
    def __init__(
        self,
        message: str,
        errors: Optional[List[Dict[str, Any]]] = None,
        code: str = "VALIDATION_ERROR"
    ):
        details = {"errors": errors or []}
        super().__init__(message, code, status.HTTP_400_BAD_REQUEST, details)


class AuthenticationError(ServiceException):
    """Ошибка аутентификации."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        code: str = "AUTHENTICATION_ERROR"
    ):
        super().__init__(message, code, status.HTTP_401_UNAUTHORIZED)


class AuthorizationError(ServiceException):
    """Ошибка авторизации."""
    
    def __init__(
        self,
        message: str = "Insufficient permissions",
        code: str = "AUTHORIZATION_ERROR"
    ):
        super().__init__(message, code, status.HTTP_403_FORBIDDEN)


class NotFoundError(ServiceException):
    """Ресурс не найден."""
    
    def __init__(
        self,
        resource: str,
        resource_id: Optional[Any] = None,
        code: str = "NOT_FOUND"
    ):
        message = f"{resource} not found"
        if resource_id is not None:
            message = f"{resource} with id {resource_id} not found"
        
        details = {"resource": resource, "resource_id": resource_id}
        super().__init__(message, code, status.HTTP_404_NOT_FOUND, details)


class ConflictError(ServiceException):
    """Конфликт (например, дублирование уникальных данных)."""
    
    def __init__(
        self,
        message: str = "Resource conflict",
        code: str = "CONFLICT"
    ):
        super().__init__(message, code, status.HTTP_409_CONFLICT)


class RateLimitError(ServiceException):
    """Превышен лимит запросов."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        code: str = "RATE_LIMIT_EXCEEDED"
    ):
        super().__init__(message, code, status.HTTP_429_TOO_MANY_REQUESTS)


class ExternalServiceError(ServiceException):
    """Ошибка при обращении к внешнему сервису."""
    
    def __init__(
        self,
        service: str,
        message: Optional[str] = None,
        code: str = "EXTERNAL_SERVICE_ERROR"
    ):
        message = message or f"Error communicating with {service} service"
        details = {"service": service}
        super().__init__(message, code, status.HTTP_502_BAD_GATEWAY, details)


class DatabaseError(ServiceException):
    """Ошибка базы данных."""
    
    def __init__(
        self,
        message: str = "Database error",
        code: str = "DATABASE_ERROR"
    ):
        super().__init__(message, code, status.HTTP_500_INTERNAL_SERVER_ERROR)


class BusinessLogicError(ServiceException):
    """Ошибка бизнес-логики."""
    
    def __init__(
        self,
        message: str,
        code: str = "BUSINESS_LOGIC_ERROR"
    ):
        super().__init__(message, code, status.HTTP_422_UNPROCESSABLE_ENTITY)