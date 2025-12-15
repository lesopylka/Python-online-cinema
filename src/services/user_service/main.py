"""
Основной файл User Service.
"""

import logging
from datetime import datetime
from uuid import UUID
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.config.database import get_db, engine
from src.config.settings import settings
from src.shared.logging import setup_logging
from src.shared.exceptions import ServiceException
from src.shared.schemas import (
    PaginatedResponse, SuccessResponse, ErrorResponse,
    HealthCheck, Status
)
from src.monitoring.metrics import setup_metrics
from src.monitoring.tracing import setup_tracing

from . import models, schemas, crud, dependencies
from .models import Base

# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)

# Создание таблиц
Base.metadata.create_all(bind=engine)

# Создание приложения
app = FastAPI(
    title="User Service",
    description="Сервис управления пользователями онлайн-кинотеатра",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройка метрик
setup_metrics(app)

# Настройка трассировки
setup_tracing(app)


# ====== Exception handlers ======

@app.exception_handler(ServiceException)
async def service_exception_handler(request: Request, exc: ServiceException):
    """Обработчик кастомных исключений."""
    logger.warning(f"Service exception: {exc.message}", extra={"code": exc.code})
    
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=exc.message,
            code=exc.code,
            errors=exc.details.get("errors") if "errors" in exc.details else None
        ).dict()
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Обработчик HTTP исключений."""
    logger.warning(f"HTTP exception: {exc.detail}")
    
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            detail=exc.detail,
            status_code=exc.status_code
        ).dict()
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Обработчик непредвиденных исключений."""
    logger.exception(f"Unexpected error: {str(exc)}")
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            detail="Internal server error",
            code="INTERNAL_ERROR"
        ).dict()
    )


# ====== Health check ======

@app.get("/", include_in_schema=False)
async def root():
    """Корневой endpoint."""
    return {
        "message": "User Service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)) -> HealthCheck:
    """
    Health check endpoint.
    Проверяет подключение к базе данных и другим зависимостям.
    """
    dependencies_status = {}
    
    # Проверка базы данных
    try:
        db.execute("SELECT 1")
        dependencies_status["database"] = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        dependencies_status["database"] = "unhealthy"
    
    # Проверка Redis (можно добавить позже)
    # Проверка Kafka (можно добавить позже)
    
    return HealthCheck(
        status="healthy" if all(v == "healthy" for v in dependencies_status.values()) else "degraded",
        service="user-service",
        version="1.0.0",
        dependencies=dependencies_status
    )


# ====== Authentication endpoints ======

@app.post("/api/v1/auth/register", response_model=SuccessResponse[schemas.UserResponse])
async def register(
    request: Request,
    user: schemas.UserCreate,
    db: Session = Depends(get_db),
    client_info: dict = Depends(dependencies.get_client_info)
):
    """
    Регистрация нового пользователя.
    
    Args:
        user: Данные для регистрации
        db: Сессия базы данных
        client_info: Информация о клиенте
        
    Returns:
        Данные созданного пользователя
    """
    logger.info(f"Registration attempt for email: {user.email}")
    
    db_user = crud.create_user(
        db=db,
        user=user,
        ip_address=client_info.get("ip_address")
    )
    
    # Создание токенов
    access_token = crud.create_access_token({
        "sub": str(db_user.id),
        "email": db_user.email,
        "role": db_user.role.value,
        "permissions": []
    })
    
    refresh_token = crud.create_refresh_token({
        "sub": str(db_user.id)
    })
    
    # Создание сессии
    crud.create_user_session(
        db=db,
        user_id=db_user.id,
        access_token=access_token,
        refresh_token=refresh_token,
        user_agent=client_info.get("user_agent"),
        ip_address=client_info.get("ip_address")
    )
    
    # Создание токена верификации email
    crud.create_email_verification(db, db_user.id, db_user.email)
    
    user_response = schemas.UserResponse.from_orm(db_user)
    
    return SuccessResponse[schemas.UserResponse](
        message="Registration successful",
        data={
            "user": user_response,
            "token": {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }
        }
    )


@app.post("/api/v1/auth/login", response_model=SuccessResponse)
async def login(
    request: Request,
    login_data: schemas.UserLogin,
    db: Session = Depends(get_db),
    client_info: dict = Depends(dependencies.get_client_info)
):
    """
    Аутентификация пользователя.
    
    Args:
        login_data: Данные для входа
        db: Сессия базы данных
        client_info: Информация о клиенте
        
    Returns:
        Токены аутентификации
    """
    logger.info(f"Login attempt: {login_data.email or login_data.username}")
    
    user = crud.authenticate_user(
        db=db,
        login_data=login_data,
        ip_address=client_info.get("ip_address"),
        user_agent=client_info.get("user_agent")
    )
    
    # Создание токенов
    access_token = crud.create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "role": user.role.value,
        "permissions": []
    })
    
    refresh_token = crud.create_refresh_token({
        "sub": str(user.id)
    })
    
    # Создание сессии
    crud.create_user_session(
        db=db,
        user_id=user.id,
        access_token=access_token,
        refresh_token=refresh_token,
        user_agent=client_info.get("user_agent"),
        ip_address=client_info.get("ip_address")
    )
    
    user_response = schemas.UserResponse.from_orm(user)
    
    return SuccessResponse(
        message="Login successful",
        data={
            "user": user_response,
            "token": {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            }
        }
    )


@app.post("/api/v1/auth/refresh", response_model=SuccessResponse)
async def refresh_token(
    request: Request,
    db: Session = Depends(get_db),
    client_info: dict = Depends(dependencies.get_client_info)
):
    """
    Обновление access токена.
    
    Requires:
        Refresh токен в заголовке Authorization
        
    Returns:
        Новый access токен
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token"
        )
    
    refresh_token = auth_header.split(" ")[1]
    
    tokens = crud.refresh_access_token(
        db=db,
        refresh_token=refresh_token,
        ip_address=client_info.get("ip_address"),
        user_agent=client_info.get("user_agent")
    )
    
    return SuccessResponse(
        message="Token refreshed",
        data=tokens
    )


@app.post("/api/v1/auth/logout")
async def logout(
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Выход пользователя из системы.
    
    Requires:
        Аутентификация
    """
    # Получаем токен из заголовка
    auth_header = request.headers.get("Authorization")
    token = auth_header.split(" ")[1] if auth_header and auth_header.startswith("Bearer ") else None
    
    crud.logout_user(
        db=db,
        user_id=current_user.id,
        token=token
    )
    
    return SuccessResponse(
        message="Logout successful"
    )


@app.post("/api/v1/auth/logout/all")
async def logout_all(
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Выход из всех устройств.
    
    Requires:
        Аутентификация
    """
    crud.logout_user(db=db, user_id=current_user.id)
    
    return SuccessResponse(
        message="Logged out from all devices"
    )


# ====== User management endpoints ======

@app.get("/api/v1/users/me", response_model=SuccessResponse[schemas.UserResponse])
async def read_current_user(
    current_user: models.User = Depends(dependencies.get_current_user)
):
    """
    Получение данных текущего пользователя.
    
    Requires:
        Аутентификация
    """
    return SuccessResponse[schemas.UserResponse](
        message="User data retrieved",
        data=schemas.UserResponse.from_orm(current_user)
    )


@app.put("/api/v1/users/me", response_model=SuccessResponse[schemas.UserResponse])
async def update_current_user(
    user_update: schemas.UserUpdate,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Обновление данных текущего пользователя.
    
    Requires:
        Аутентификация
    """
    updated_user = crud.update_user(
        db=db,
        user_id=current_user.id,
        user_update=user_update,
        current_user_id=current_user.id
    )
    
    return SuccessResponse[schemas.UserResponse](
        message="User updated",
        data=schemas.UserResponse.from_orm(updated_user)
    )


@app.post("/api/v1/users/me/password", response_model=SuccessResponse)
async def change_password(
    password_change: schemas.PasswordChange,
    current_user: models.User = Depends(dependencies.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Изменение пароля текущего пользователя.
    
    Requires:
        Аутентификация
    """
    crud.change_password(
        db=db,
        user_id=current_user.id,
        password_change=password_change
    )
    
    return SuccessResponse(
        message="Password changed successfully"
    )


@app.get("/api/v1/users/{user_id}", response_model=SuccessResponse[schemas.UserProfileResponse])
async def read_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.get_current_user_optional)
):
    """
    Получение публичного профиля пользователя.
    
    Args:
        user_id: ID пользователя
        
    Returns:
        Публичный профиль пользователя
    """
    user = crud.get_user(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # Проверяем права доступа
    if current_user and (current_user.id == user.id or current_user.role == schemas.UserRole.ADMIN):
        # Показываем полный профиль владельцу или администратору
        response_data = schemas.UserResponse.from_orm(user)
    else:
        # Показываем публичный профиль
        response_data = schemas.UserProfileResponse.from_orm(user)
    
    return SuccessResponse(
        message="User profile retrieved",
        data=response_data
    )


@app.get("/api/v1/users", response_model=SuccessResponse[PaginatedResponse[schemas.UserResponse]])
async def read_users(
    pagination: dict = Depends(dependencies.get_pagination_params),
    filters: dict = Depends(dependencies.get_user_filters),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(dependencies.require_admin)
):
    """
    Получение списка пользователей.
    
    Requires:
        Администратор
        
    Query Parameters:
        page: Номер страницы
        size: Размер страницы
        email: Фильтр по email
        username: Фильтр по username
        role: Фильтр по роли
        status: Фильтр по статусу
    """
    users = crud.get_users(
        db=db,
        skip=pagination["skip"],
        limit=pagination["size"],
        filters=filters
    )
    
    total = crud.count_users(db, filters)
    
    user_responses = [schemas.UserResponse.from_orm(user) for user in users]
    
    paginated_response = PaginatedResponse[schemas.UserResponse](
        items=user_responses,
        total=total,
        page=pagination["page"],
        size=pagination["size"]
    )
    
    return SuccessResponse[PaginatedResponse[schemas.UserResponse]](
        message="Users retrieved",
        data=paginated_response
    )


# ====== Email verification ======

@app.post("/api/v1/auth/verify/email/request")
async def request_email_verification(
    request_data: schemas.EmailVerificationRequest,
    db: Session = Depends(get_db)
):
    """
    Запрос верификации email.
    
    Args:
        request_data: Данные для запроса верификации
    """
    user = crud.get_user_by_email(db, request_data.email)
    if not user:
        # Не раскрываем, что пользователь не найден
        return SuccessResponse(
            message="If the email exists, a verification link has been sent"
        )
    
    crud.create_email_verification(db, user.id, user.email)
    
    return SuccessResponse(
        message="If the email exists, a verification link has been sent"
    )


@app.post("/api/v1/auth/verify/email/confirm")
async def confirm_email_verification(
    verification_data: schemas.EmailVerificationConfirm,
    db: Session = Depends(get_db)
):
    """
    Подтверждение верификации email.
    
    Args:
        verification_data: Данные для подтверждения
    """
    crud.verify_email(db, verification_data.token)
    
    return SuccessResponse(
        message="Email verified successfully"
    )


# ====== Password reset ======

@app.post("/api/v1/auth/password/reset/request")
async def request_password_reset(
    request_data: schemas.PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    Запрос сброса пароля.
    
    Args:
        request_data: Данные для запроса сброса
    """
    crud.create_password_reset(db, request_data.email)
    
    return SuccessResponse(
        message="If the email exists, a reset link has been sent"
    )


@app.post("/api/v1/auth/password/reset/confirm")
async def confirm_password_reset(
    reset_data: schemas.PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """
    Подтверждение сброса пароля.
    
    Args:
        reset_data: Данные для подтверждения сброса
    """
    crud.reset_password(db, reset_data.token, reset_data.new_password)
    
    return SuccessResponse(
        message="Password reset successfully"
    )


# ====== Admin endpoints ======

@app.put("/api/v1/admin/users/{user_id}/role", response_model=SuccessResponse[schemas.UserResponse])
async def update_user_role(
    user_id: UUID,
    role_update: schemas.UserRole,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(dependencies.require_admin)
):
    """
    Обновление роли пользователя.
    
    Requires:
        Администратор
        
    Args:
        user_id: ID пользователя
        role_update: Новая роль
    """
    updated_user = crud.update_user_role(
        db=db,
        user_id=user_id,
        new_role=role_update,
        admin_user_id=admin_user.id
    )
    
    return SuccessResponse[schemas.UserResponse](
        message="User role updated",
        data=schemas.UserResponse.from_orm(updated_user)
    )


@app.put("/api/v1/admin/users/{user_id}/status", response_model=SuccessResponse[schemas.UserResponse])
async def update_user_status(
    user_id: UUID,
    status_update: schemas.UserStatus,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(dependencies.require_admin)
):
    """
    Обновление статуса пользователя.
    
    Requires:
        Администратор
        
    Args:
        user_id: ID пользователя
        status_update: Новый статус
    """
    updated_user = crud.update_user_status(
        db=db,
        user_id=user_id,
        new_status=status_update,
        admin_user_id=admin_user.id
    )
    
    return SuccessResponse[schemas.UserResponse](
        message="User status updated",
        data=schemas.UserResponse.from_orm(updated_user)
    )


@app.delete("/api/v1/admin/users/{user_id}")
async def delete_user_admin(
    user_id: UUID,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(dependencies.require_admin)
):
    """
    Удаление пользователя (администратором).
    
    Requires:
        Администратор
        
    Args:
        user_id: ID пользователя для удаления
    """
    crud.delete_user(db, user_id, admin_user.id)
    
    return SuccessResponse(
        message="User deleted successfully"
    )


# ====== Event handlers ======

@app.on_event("startup")
async def startup_event():
    """Действия при запуске сервиса."""
    logger.info("Starting User Service...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Database URL: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else settings.DATABASE_URL}")


@app.on_event("shutdown")
async def shutdown_event():
    """Действия при остановке сервиса."""
    logger.info("Shutting down User Service...")