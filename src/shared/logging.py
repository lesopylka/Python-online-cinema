"""
Конфигурация логирования для всех сервисов.
"""

import logging
import sys
import json
from logging.handlers import RotatingFileHandler
from typing import Dict, Any
from datetime import datetime
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
        }
        
        # Добавляем дополнительные поля из record
        if hasattr(record, "extra"):
            log_data.update(record.extra)
        
        # Добавляем информацию об исключении
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


def setup_logging():
    """
    Настройка логирования для приложения.
    Создает консольный и файловый хэндлеры.
    """
    
    # Определяем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # Очищаем существующие хэндлеры
    root_logger.handlers.clear()
    
    # Форматеры
    json_formatter = JSONFormatter()
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Консольный хэндлер
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(simple_formatter)
    console_handler.setLevel(logging.INFO)
    
    # Файловый хэндлер (JSON)
    file_handler = RotatingFileHandler(
        f'logs/{settings.ENVIRONMENT}.log',
        maxBytes=10485760,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setFormatter(json_formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Хэндлер для ошибок
    error_handler = RotatingFileHandler(
        f'logs/{settings.ENVIRONMENT}.error.log',
        maxBytes=10485760,
        backupCount=10,
        encoding='utf-8'
    )
    error_handler.setFormatter(json_formatter)
    error_handler.setLevel(logging.ERROR)
    
    # Добавляем хэндлеры
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    
    # Устанавливаем уровни для сторонних библиотек
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("kafka").setLevel(logging.WARNING)
    logging.getLogger("elasticsearch").setLevel(logging.WARNING)
    
    # Логируем начало работы
    root_logger.info(
        "Logging configured",
        extra={
            "environment": settings.ENVIRONMENT,
            "log_level": settings.LOG_LEVEL
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
    logger = logging.getLogger(name)
    return logger


# Декоратор для логирования вызовов функций
def log_call(logger_name: str = None):
    """
    Декоратор для логирования вызовов функций.
    
    Args:
        logger_name: Имя логгера (если None, используется имя модуля)
    """
    def decorator(func):
        nonlocal logger_name
        if logger_name is None:
            logger_name = func.__module__
        
        logger = get_logger(logger_name)
        
        def wrapper(*args, **kwargs):
            logger.debug(
                f"Calling {func.__name__}",
                extra={
                    "function": func.__name__,
                    "args": str(args),
                    "kwargs": str(kwargs)
                }
            )
            
            try:
                result = func(*args, **kwargs)
                logger.debug(
                    f"Function {func.__name__} completed successfully",
                    extra={"function": func.__name__}
                )
                return result
            except Exception as e:
                logger.error(
                    f"Function {func.__name__} failed: {str(e)}",
                    extra={
                        "function": func.__name__,
                        "error": str(e),
                        "error_type": type(e).__name__
                    },
                    exc_info=True
                )
                raise
        
        return wrapper
    
    return decorator