"""
Клиент для отправки сообщений в Kafka.
"""

import json
import logging
from kafka import KafkaProducer
from kafka.errors import KafkaError
from typing import Any, Dict, Optional, Callable
from functools import wraps
from datetime import datetime
from src.config.settings import settings

logger = logging.getLogger(__name__)


class KafkaProducerClient:
    """
    Клиент для работы с Kafka Producer.
    
    Attributes:
        producer: Kafka Producer instance
        connected: Флаг подключения
    """
    
    def __init__(self):
        self.producer = None
        self.connected = False
        self._connect()
    
    def _connect(self):
        """Подключение к Kafka."""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(','),
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: str(k).encode('utf-8') if k else None,
                acks='all',  # Гарантированная запись
                retries=3,   # Количество попыток
                max_in_flight_requests_per_connection=1,  # Гарантия порядка
                compression_type='gzip',  # Сжатие сообщений
                linger_ms=5,  # Задержка перед отправкой (батчинг)
                batch_size=16384,  # Размер батча
            )
            self.connected = True
            logger.info("Connected to Kafka")
            
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            self.connected = False
    
    def send(
        self,
        topic: str,
        value: Dict[str, Any],
        key: Optional[str] = None,
        callback: Optional[Callable] = None
    ) -> bool:
        """
        Отправка сообщения в Kafka.
        
        Args:
            topic: Название топика
            value: Данные для отправки
            key: Ключ для партиционирования
            callback: Функция обратного вызова
            
        Returns:
            True если сообщение отправлено успешно
        """
        if not self.connected or not self.producer:
            logger.warning("Kafka producer not connected")
            return False
        
        try:
            # Добавляем метаданные
            enriched_value = {
                **value,
                "_metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "producer": "online-cinema",
                    "environment": settings.ENVIRONMENT
                }
            }
            
            future = self.producer.send(
                topic=topic,
                value=enriched_value,
                key=key
            )
            
            # Добавляем callback если указан
            if callback:
                future.add_callback(
                    lambda metadata: callback(True, metadata)
                ).add_errback(
                    lambda error: callback(False, error)
                )
            else:
                # Используем стандартные callback
                future.add_callback(self._on_send_success).add_errback(self._on_send_error)
            
            logger.debug(
                f"Sent message to topic {topic}",
                extra={
                    "topic": topic,
                    "key": key,
                    "value_size": len(json.dumps(value))
                }
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send message to Kafka: {e}")
            return False
    
    def send_sync(
        self,
        topic: str,
        value: Dict[str, Any],
        key: Optional[str] = None,
        timeout: int = 10
    ) -> bool:
        """
        Синхронная отправка сообщения с ожиданием подтверждения.
        
        Args:
            topic: Название топика
            value: Данные для отправки
            key: Ключ для партиционирования
            timeout: Таймаут ожидания
            
        Returns:
            True если сообщение подтверждено
        """
        if not self.connected or not self.producer:
            logger.warning("Kafka producer not connected")
            return False
        
        try:
            enriched_value = {
                **value,
                "_metadata": {
                    "timestamp": datetime.utcnow().isoformat(),
                    "producer": "online-cinema",
                    "environment": settings.ENVIRONMENT
                }
            }
            
            future = self.producer.send(
                topic=topic,
                value=enriched_value,
                key=key
            )
            
            # Ожидаем подтверждение
            record_metadata = future.get(timeout=timeout)
            
            logger.info(
                f"Message confirmed: {record_metadata.topic} "
                f"[{record_metadata.partition}] @{record_metadata.offset}"
            )
            
            return True
            
        except KafkaError as e:
            logger.error(f"Kafka error sending message: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending message: {e}")
            return False
    
    def flush(self):
        """Ожидание отправки всех сообщений."""
        if self.producer:
            self.producer.flush()
    
    def close(self):
        """Закрытие соединения с Kafka."""
        if self.producer:
            self.producer.close()
            self.connected = False
            logger.info("Kafka producer closed")
    
    def _on_send_success(self, record_metadata):
        """Callback при успешной отправке."""
        logger.debug(
            f"Message sent to {record_metadata.topic} "
            f"[{record_metadata.partition}] @{record_metadata.offset}",
            extra={
                "topic": record_metadata.topic,
                "partition": record_metadata.partition,
                "offset": record_metadata.offset
            }
        )
    
    def _on_send_error(self, error):
        """Callback при ошибке отправки."""
        logger.error(f"Error sending message to Kafka: {error}")


# Глобальный инстанс продюсера
_kafka_producer: Optional[KafkaProducerClient] = None


def get_kafka_producer() -> KafkaProducerClient:
    """
    Получение глобального инстанса Kafka продюсера.
    
    Returns:
        KafkaProducerClient instance
    """
    global _kafka_producer
    if _kafka_producer is None:
        _kafka_producer = KafkaProducerClient()
    return _kafka_producer


def send_kafka_message(
    topic: str,
    value: Dict[str, Any],
    key: Optional[str] = None,
    sync: bool = False
) -> bool:
    """
    Упрощенная функция для отправки сообщений в Kafka.
    
    Args:
        topic: Название топика
        value: Данные для отправки
        key: Ключ для партиционирования
        sync: Синхронная отправка
        
    Returns:
        True если сообщение отправлено успешно
    """
    producer = get_kafka_producer()
    
    if sync:
        return producer.send_sync(topic, value, key)
    else:
        return producer.send(topic, value, key)


# Декоратор для отправки событий в Kafka
def kafka_event(topic: str, key_field: Optional[str] = None):
    """
    Декоратор для автоматической отправки событий в Kafka.
    
    Args:
        topic: Топик для отправки события
        key_field: Поле для использования в качестве ключа
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Выполняем функцию
            result = func(*args, **kwargs)
            
            try:
                # Формируем событие
                event = {
                    "event_type": func.__name__,
                    "timestamp": datetime.utcnow().isoformat(),
                    "result": result if isinstance(result, dict) else str(result)
                }
                
                # Определяем ключ
                key = None
                if key_field and isinstance(result, dict):
                    key = result.get(key_field)
                
                # Отправляем событие
                send_kafka_message(topic, event, key)
                
            except Exception as e:
                logger.warning(f"Failed to send Kafka event: {e}")
            
            return result
        
        return wrapper
    
    return decorator