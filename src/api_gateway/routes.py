import time
import json
import logging
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, StreamingResponse
from typing import Callable, Optional, Dict, Any
import jwt
from src.config.settings import settings
from src.monitoring.metrics import record_service_metrics

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware для логирования входящих запросов и исходящих ответов.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Начало измерения времени
        start_time = time.time()
        
        # Логирование входящего запроса
        request_info = await self._get_request_info(request)
        logger.info(f"Incoming request: {request_info}")
        
        try:
            # Обработка запроса
            response = await call_next(request)
            
            # Логирование ответа
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)
            
            logger.info(
                f"Response: {request.method} {request.url.path} "
                f"Status: {response.status_code} "
                f"Time: {process_time:.3f}s"
            )
            
            return response
            
        except Exception as e:
            # Логирование ошибок
            process_time = time.time() - start_time
            logger.error(
                f"Request failed: {request.method} {request.url.path} "
                f"Error: {str(e)} "
                f"Time: {process_time:.3f}s"
            )
            raise
    
    async def _get_request_info(self, request: Request) -> Dict[str, Any]:
        """Получение информации о запросе для логирования."""
        info = {
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }
        
        # Безопасное получение тела запроса
        try:
            if request.method in ["POST", "PUT", "PATCH"]:
                body = await request.body()
                if body:
                    info["body_size"] = len(body)
                    
                    # Для JSON запросов логируем структуру
                    content_type = request.headers.get("content-type", "")
                    if "application/json" in content_type:
                        try:
                            info["body"] = json.loads(body.decode())[:1000]  # Ограничиваем размер
                        except:
                            info["body"] = "Unable to parse JSON"
        except:
            pass
        
        return info


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware для проверки аутентификации и авторизации.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Публичные endpoints
        public_paths = [
            "/", "/health", "/docs", "/redoc", "/openapi.json", "/metrics",
            "/api/v1/auth/login", "/api/v1/auth/register", "/api/v1/auth/refresh"
        ]
        
        if request.url.path in public_paths or request.url.path.startswith("/api/v1/auth/"):
            return await call_next(request)
        
        # Проверка токена
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Missing or invalid authorization header"
            )
        
        token = auth_header.split(" ")[1]
        
        try:
            # Верификация JWT токена
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM]
            )
            
            # Сохраняем данные пользователя в request state
            request.state.user_id = payload.get("sub")
            request.state.user_email = payload.get("email")
            request.state.user_roles = payload.get("roles", [])
            request.state.user_permissions = payload.get("permissions", [])
            
            # Добавляем информацию в заголовки для внутренних сервисов
            request.headers.__dict__["_list"].append(
                (b"x-user-id", str(payload.get("sub")).encode())
            )
            request.headers.__dict__["_list"].append(
                (b"x-user-roles", json.dumps(payload.get("roles", [])).encode())
            )
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jwt.InvalidTokenError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
        
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware для ограничения количества запросов (простая реализация).
    В production следует использовать Redis или специализированные решения.
    """
    
    def __init__(self, app, limit: int = 100, window: int = 60):
        super().__init__(app)
        self.limit = limit
        self.window = window
        self.requests = {}  # {ip: [timestamp1, timestamp2, ...]}
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Очистка старых записей
        self._cleanup_old_requests(current_time)
        
        # Проверка лимита
        if client_ip in self.requests:
            request_times = self.requests[client_ip]
            if len(request_times) >= self.limit:
                # Слишком много запросов
                raise HTTPException(
                    status_code=429,
                    detail=f"Too many requests. Limit: {self.limit} per {self.window} seconds",
                    headers={
                        "X-RateLimit-Limit": str(self.limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(request_times[0] + self.window))
                    }
                )
            
            request_times.append(current_time)
        else:
            self.requests[client_ip] = [current_time]
        
        # Расчет оставшихся запросов
        if client_ip in self.requests:
            remaining = self.limit - len(self.requests[client_ip])
            reset_time = int(self.requests[client_ip][0] + self.window)
        else:
            remaining = self.limit
            reset_time = int(current_time + self.window)
        
        # Добавляем заголовки rate limit
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        
        return response
    
    def _cleanup_old_requests(self, current_time: float):
        """Очистка запросов старше window секунд."""
        cutoff_time = current_time - self.window
        
        for ip in list(self.requests.keys()):
            self.requests[ip] = [
                t for t in self.requests[ip]
                if t > cutoff_time
            ]
            
            if not self.requests[ip]:
                del self.requests[ip]


class ServiceMetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware для сбора метрик по вызовам сервисов.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Определяем сервис по пути
            service_name = self._get_service_name(request.url.path)
            if service_name:
                record_service_metrics(service_name, duration, True)
            
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            service_name = self._get_service_name(request.url.path)
            if service_name:
                record_service_metrics(service_name, duration, False)
            raise
    
    def _get_service_name(self, path: str) -> Optional[str]:
        """Определение имени сервиса по пути запроса."""
        if path.startswith("/api/v1/auth/") or path.startswith("/api/v1/users/"):
            return "user-service"
        elif path.startswith("/api/v1/movies/"):
            return "catalog-service"
        elif path.startswith("/api/v1/search/"):
            return "search-service"
        elif path.startswith("/api/v1/stream/"):
            return "streaming-service"
        elif path.startswith("/api/v1/analytics/"):
            return "analytics-service"
        return None