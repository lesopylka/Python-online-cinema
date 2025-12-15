"""
Конфигурация логирования для всех сервисов.
Используется стандартный Python logging с ротацией файлов.
"""

import logging
import sys
import json
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
from typing import Dict, Any
import os

from src.config.settings import settings


class JSONFormatter(logging.Formatter):
    """Форматтер для вывода логов в JSON формате."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process_id": record.process,
            "thread_id": record.thread,
        }
        
        # Добавляем контекст из record.extra если есть
        if hasattr(record, 'extra'):
            log_data.update(record.extra)
        
        # Добавляем информацию об исключении
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info)
            }
        
        # Добавляем информацию о запросе если есть
        if hasattr(record, 'request_id'):
            log_data["request_id"] = record.request_id
        if hasattr(record, 'user_id'):
            log_data["user_id"] = record.user_id
        if hasattr(record, 'ip_address'):
            log_data["ip_address"] = record.ip_address
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class StructuredFormatter(logging.Formatter):
    """Структурированный форматтер для читаемого вывода."""
    
    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
        
        # Базовый формат
        log_line = f"{timestamp} - {record.name} - {record.levelname} - {record.getMessage()}"
        
        # Добавляем дополнительный контекст
        extra_info = []
        if hasattr(record, 'request_id'):
            extra_info.append(f"req_id={record.request_id}")
        if hasattr(record, 'user_id'):
            extra_info.append(f"user_id={record.user_id}")
        if hasattr(record, 'ip_address'):
            extra_info.append(f"ip={record.ip_address}")
        if hasattr(record, 'duration'):
            extra_info.append(f"duration={record.duration:.3f}s")
        
        if extra_info:
            log_line += f" [{' '.join(extra_info)}]"
        
        # Добавляем информацию об исключении
        if record.exc_info:
            log_line += f"\n{self.formatException(record.exc_info)}"
        
        return log_line


def setup_logging(service_name: str = None):
    """
    Настройка логирования для сервиса.
    
    Args:
        service_name: Название сервиса (для именования файлов)
    """
    
    # Создаем директорию для логов если не существует
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Определяем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # Очищаем существующие хэндлеры
    root_logger.handlers.clear()
    
    # Форматеры
    json_formatter = JSONFormatter()
    console_formatter = StructuredFormatter()
    
    # Консольный хэндлер (всегда включен)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    
    # Файловый хэндлер для всех логов (JSON формат)
    if service_name:
        log_filename = f"{log_dir}/{service_name}.log"
    else:
        log_filename = f"{log_dir}/application.log"
    
    file_handler = RotatingFileHandler(
        filename=log_filename,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setFormatter(json_formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Хэндлер для ошибок (отдельный файл)
    if service_name:
        error_filename = f"{log_dir}/{service_name}.error.log"
    else:
        error_filename = f"{log_dir}/error.log"
    
    error_handler = RotatingFileHandler(
        filename=error_filename,
        maxBytes=10 * 1024 * 1024,
        backupCount=10,
        encoding='utf-8'
    )
    error_handler.setFormatter(json_formatter)
    error_handler.setLevel(logging.ERROR)
    
    # Хэндлер для аудита (действия пользователей)
    if service_name:
        audit_filename = f"{log_dir}/{service_name}.audit.log"
    else:
        audit_filename = f"{log_dir}/audit.log"
    
    audit_handler = TimedRotatingFileHandler(
        filename=audit_filename,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    audit_handler.setFormatter(json_formatter)
    audit_handler.setLevel(logging.INFO)
    
    # Добавляем фильтр для аудит логов
    class AuditFilter(logging.Filter):
        def filter(self, record):
            return hasattr(record, 'audit') and record.audit
    
    audit_handler.addFilter(AuditFilter())
    
    # Добавляем все хэндлеры
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(audit_handler)
    
    # Устанавливаем уровни для сторонних библиотек
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("kafka").setLevel(logging.WARNING)
    logging.getLogger("elasticsearch").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)
    logging.getLogger("aiokafka").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    # Логируем начало работы
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured",
        extra={
            "environment": settings.ENVIRONMENT,
            "log_level": settings.LOG_LEVEL,
            "service": service_name or "unknown"
        }
    )


def get_logger(name: str) -> logging.Logger:
    """
    Получение логгера с указанным именем.
    
    Args:
        name: Имя логгера
        
    Returns:
        Настроенный логгер
    """
    return logging.getLogger(name)


class RequestLogger:
    """Класс для логирования запросов с контекстом."""
    
    def __init__(self, logger_name: str = "request"):
        self.logger = get_logger(logger_name)
    
    def log_request(
        self,
        request_id: str,
        method: str,
        path: str,
        user_id: str = None,
        ip_address: str = None,
        user_agent: str = None
    ):
        """Логирование входящего запроса."""
        self.logger.info(
            f"Request started: {method} {path}",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "user_id": user_id,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "event": "request_started"
            }
        )
    
    def log_response(
        self,
        request_id: str,
        method: str,
        path: str,
        status_code: int,
        duration: float,
        user_id: str = None
    ):
        """Логирование ответа на запрос."""
        self.logger.info(
            f"Request completed: {method} {path} {status_code} ({duration:.3f}s)",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration": duration,
                "user_id": user_id,
                "event": "request_completed"
            }
        )
    
    def log_error(
        self,
        request_id: str,
        method: str,
        path: str,
        error: Exception,
        status_code: int = 500,
        user_id: str = None
    ):
        """Логирование ошибки при обработке запроса."""
        self.logger.error(
            f"Request failed: {method} {path} {status_code} - {str(error)}",
            extra={
                "request_id": request_id,
                "method": method,
                "path": path,
                "status_code": status_code,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "user_id": user_id,
                "event": "request_failed"
            },
            exc_info=True
        )
    
    def log_audit(
        self,
        action: str,
        user_id: str,
        resource_type: str = None,
        resource_id: str = None,
        details: Dict[str, Any] = None,
        ip_address: str = None
    ):
        """Логирование аудиторских событий."""
        self.logger.info(
            f"Audit: {action} by user {user_id}",
            extra={
                "audit": True,
                "action": action,
                "user_id": user_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "details": details or {},
                "ip_address": ip_address,
                "timestamp": datetime.utcnow().isoformat(),
                "event": "audit_event"
            }
        )


# Глобальный инстанс для логирования запросов
request_logger = RequestLogger()