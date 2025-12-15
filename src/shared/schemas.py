from pydantic import BaseModel, Field, validator
from typing import TypeVar, Generic, List, Optional, Any, Dict
from datetime import datetime
from enum import Enum

T = TypeVar('T')

class Status(str, Enum):
    """Статусы операций."""
    SUCCESS = "success"
    ERROR = "error"
    PENDING = "pending"

class PaginatedResponse(BaseModel, Generic[T]):
    """
    Стандартная схема для пагинированных ответов.
    
    Attributes:
        items: Список элементов на текущей странице
        total: Общее количество элементов
        page: Текущая страница (начинается с 1)
        size: Количество элементов на странице
        pages: Общее количество страниц
        has_next: Есть ли следующая страница
        has_prev: Есть ли предыдущая страница
    """
    items: List[T]
    total: int
    page: int = Field(ge=1, default=1)
    size: int = Field(ge=1, le=100, default=20)
    pages: int
    has_next: bool
    has_prev: bool
    
    @validator('pages', always=True)
    def calculate_pages(cls, v, values):
        """Вычисление общего количества страниц."""
        if 'total' in values and 'size' in values:
            total = values['total']
            size = values['size']
            return (total + size - 1) // size  # ceil division
        return v
    
    @validator('has_next', always=True)
    def calculate_has_next(cls, v, values):
        """Вычисление наличия следующей страницы."""
        if 'page' in values and 'pages' in values:
            return values['page'] < values['pages']
        return False
    
    @validator('has_prev', always=True)
    def calculate_has_prev(cls, v, values):
        """Вычисление наличия предыдущей страницы."""
        if 'page' in values:
            return values['page'] > 1
        return False


class ErrorResponse(BaseModel):
    """
    Стандартная схема для ошибок.
    
    Attributes:
        detail: Сообщение об ошибке
        code: Код ошибки (опционально)
        errors: Детали ошибок валидации (опционально)
        timestamp: Время возникновения ошибки
    """
    detail: str
    code: Optional[str] = None
    errors: Optional[List[Dict[str, Any]]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class SuccessResponse(BaseModel, Generic[T]):
    """
    Стандартная схема для успешных операций.
    
    Attributes:
        status: Статус операции
        message: Сообщение об операции
        data: Данные ответа (опционально)
        timestamp: Время выполнения операции
    """
    status: Status = Status.SUCCESS
    message: str
    data: Optional[T] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class HealthCheck(BaseModel):
    """
    Схема для health check endpoints.
    
    Attributes:
        status: Статус сервиса
        service: Название сервиса
        version: Версия сервиса
        timestamp: Время проверки
        dependencies: Статус зависимостей
    """
    status: str
    service: str
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    dependencies: Optional[Dict[str, Any]] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Token(BaseModel):
    """
    Схема для JWT токенов.
    
    Attributes:
        access_token: Access токен
        token_type: Тип токена (обычно 'bearer')
        expires_in: Время жизни токена в секундах
        refresh_token: Refresh токен (опционально)
    """
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: Optional[str] = None


class TokenData(BaseModel):
    """
    Схема для данных в JWT токене.
    
    Attributes:
        sub: Subject (обычно user_id)
        email: Email пользователя
        roles: Роли пользователя
        permissions: Права пользователя
        exp: Время истечения токена
    """
    sub: str
    email: str
    roles: List[str] = []
    permissions: List[str] = []
    exp: datetime
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }