"""
Настройка распределенной трассировки с использованием OpenTelemetry/Jaeger.
"""

import logging
from typing import Optional, Dict, Any
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from src.config.settings import settings

logger = logging.getLogger(__name__)

# Глобальный tracer
tracer: Optional[trace.Tracer] = None


def setup_tracing(app=None):
    """
    Настройка распределенной трассировки.
    
    Args:
        app: FastAPI приложение (опционально)
    """
    global tracer
    
    if settings.ENVIRONMENT != "production":
        logger.info("Tracing disabled in non-production environment")
        return
    
    try:
        # Создаем ресурс с атрибутами сервиса
        resource = Resource.create({
            "service.name": "online-cinema",
            "service.version": "1.0.0",
            "environment": settings.ENVIRONMENT
        })
        
        # Настраиваем провайдер трассировки
        trace.set_tracer_provider(TracerProvider(resource=resource))
        
        # Настраиваем экспортер Jaeger
        jaeger_exporter = JaegerExporter(
            agent_host_name=settings.JAEGER_HOST,
            agent_port=settings.JAEGER_PORT,
        )
        
        # Настраиваем обработчик спанов
        span_processor = BatchSpanProcessor(jaeger_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)
        
        # Получаем tracer
        tracer = trace.get_tracer(__name__)
        
        # Инструментируем приложение если передано
        if app:
            FastAPIInstrumentor.instrument_app(app)
        
        # Инструментируем HTTP клиенты
        HTTPXClientInstrumentor().instrument()
        
        # Инструментируем SQLAlchemy
        SQLAlchemyInstrumentor().instrument()
        
        # Инструментируем Redis
        RedisInstrumentor().instrument()
        
        logger.info("Tracing configured with Jaeger")
        
    except Exception as e:
        logger.error(f"Failed to setup tracing: {e}")
        tracer = None


def get_tracer():
    """
    Получение глобального tracer.
    
    Returns:
        Tracer или None если трассировка не настроена
    """
    return tracer


def trace_span(name: str, attributes: Optional[Dict[str, Any]] = None):
    """
    Декоратор для создания span трассировки.
    
    Args:
        name: Название span
        attributes: Атрибуты span
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            if tracer is None:
                return func(*args, **kwargs)
            
            with tracer.start_as_current_span(name, attributes=attributes) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("status", "success")
                    return result
                except Exception as e:
                    span.set_attribute("status", "error")
                    span.record_exception(e)
                    raise
        
        return wrapper
    
    return decorator


def add_span_attribute(key: str, value: Any):
    """
    Добавление атрибута в текущий span.
    
    Args:
        key: Ключ атрибута
        value: Значение атрибута
    """
    current_span = trace.get_current_span()
    if current_span.is_recording():
        current_span.set_attribute(key, value)


def record_span_event(name: str, attributes: Optional[Dict[str, Any]] = None):
    """
    Запись события в текущий span.
    
    Args:
        name: Название события
        attributes: Атрибуты события
    """
    current_span = trace.get_current_span()
    if current_span.is_recording():
        current_span.add_event(name, attributes=attributes)