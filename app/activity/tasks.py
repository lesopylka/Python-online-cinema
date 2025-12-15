# app/activity/tasks.py
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_activity_batch(batch_data):
    """Обработка пачки событий в фоне"""
    logger.info(f"Processing batch of {len(batch_data.get('events', []))} events")
    # Здесь будет логика обработки
    return {"status": "processed", "count": len(batch_data.get('events', []))}