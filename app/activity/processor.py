# app/activity/processor.py
import structlog
from datetime import datetime
from typing import Dict, Any
from app.schemas.activity import ActivityEvent

logger = structlog.get_logger()


class ActivityProcessor:
    @staticmethod
    async def validate_and_enrich_event(
            event_data: Dict[str, Any],
            client_ip: str,
            user_agent: str,
            request
    ) -> Dict[str, Any]:
        """Валидация и обогащение события"""
        # Базовая валидация
        required_fields = ['event_type', 'event_name']
        for field in required_fields:
            if field not in event_data:
                logger.warning(f"Missing required field: {field}")
                return None

        # Обогащение
        event_data['ip_address'] = client_ip
        event_data['user_agent'] = user_agent[:500]

        # Добавляем timestamp если нет
        if 'timestamp' not in event_data:
            event_data['timestamp'] = datetime.utcnow().isoformat()

        return event_data