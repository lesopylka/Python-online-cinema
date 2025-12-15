# app/streaming/auth.py
from fastapi import HTTPException, status
from typing import Optional


async def verify_access_token(token: Optional[str], video_id: str, request) -> bool:
    """Проверка токена доступа к видео"""
    # Заглушка для проверки
    if token == "test_token":
        return True

    # Здесь должна быть реальная логика проверки
    # Например, проверка JWT или прав пользователя

    # Временно разрешаем доступ для тестов
    return True