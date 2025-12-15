from fastapi import FastAPI, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, timedelta
from typing import List, Dict, Any
import json
from kafka import KafkaConsumer
from threading import Thread
import asyncio

from src.config.database import get_db, engine
from .models import Base, UserActivity, MovieAnalytics, WatchHistory
from src.config.settings import settings

# Создаем таблицы
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Analytics Service", version="1.0.0")

def process_activity_event(db: Session, event: Dict[str, Any]):
    """Обработка события пользовательской активности"""
    try:
        activity = UserActivity(
            user_id=event.get("user_id"),
            session_id=event.get("session_id", "unknown"),
            event_type=event.get("event_type"),
            movie_id=event.get("movie_id"),
            search_query=event.get("search_query"),
            device_type=event.get("device_type"),
            platform=event.get("platform"),
            location=event.get("location"),
            duration_seconds=event.get("duration_seconds"),
            metadata=event.get("metadata", {})
        )
        
        db.add(activity)
        
        # Обновляем аналитику фильма
        if event.get("movie_id") and event.get("event_type") in ["watch_start", "watch_end"]:
            update_movie_analytics(db, event)
        
        db.commit()
        
    except Exception as e:
        print(f"Error processing activity event: {e}")
        db.rollback()

def update_movie_analytics(db: Session, event: Dict[str, Any]):
    """Обновление аналитики фильма"""
    movie_id = event["movie_id"]
    
    # Получаем или создаем запись аналитики
    analytics = db.query(MovieAnalytics).filter(
        MovieAnalytics.movie_id == movie_id
    ).first()
    
    if not analytics:
        analytics = MovieAnalytics(movie_id=movie_id)
        db.add(analytics)
    
    if event["event_type"] == "watch_start":
        analytics.total_views += 1
        
        # Создаем или обновляем запись истории просмотра
        watch_history = WatchHistory(
            user_id=event["user_id"],
            movie_id=movie_id,
            last_position=0
        )
        db.add(watch_history)
    
    elif event["event_type"] == "watch_end":
        duration = event.get("duration_seconds", 0)
        analytics.total_watch_time += duration
        
        # Обновляем историю просмотра
        watch_history = db.query(WatchHistory).filter(
            WatchHistory.user_id == event["user_id"],
            WatchHistory.movie_id == movie_id
        ).order_by(desc(WatchHistory.watch_date)).first()
        
        if watch_history:
            watch_history.duration_watched = duration
            watch_history.completed = 1 if event.get("completed", False) else 0
            watch_history.last_position = event.get("last_position", 0)
    
    elif event["event_type"] == "review_created":
        rating = event.get("rating", 0)
        if rating > 0:
            # Обновляем средний рейтинг
            analytics.total_ratings += 1
            analytics.average_rating = (
                (analytics.average_rating * (analytics.total_ratings - 1) + rating) 
                / analytics.total_ratings
            )

def kafka_consumer_thread():
    """Поток для потребления событий из Kafka"""
    consumer = KafkaConsumer(
        'user_activity',
        bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS.split(','),
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        group_id='analytics-service-group',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )
    
    db = next(get_db())
    
    for message in consumer:
        try:
            process_activity_event(db, message.value)
        except Exception as e:
            print(f"Error in Kafka consumer: {e}")

@app.on_event("startup")
def startup_event():
    """Запуск Kafka consumer при старте"""
    thread = Thread(target=kafka_consumer_thread, daemon=True)
    thread.start()

@app.get("/api/v1/analytics/movies/popular")
def get_popular_movies(
    period_days: int = 7,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """Получение популярных фильмов за период"""
    since_date = datetime.utcnow() - timedelta(days=period_days)
    
    popular = db.query(
        UserActivity.movie_id,
        func.count(UserActivity.id).label('views')
    ).filter(
        UserActivity.event_type == 'watch_start',
        UserActivity.timestamp >= since_date,
        UserActivity.movie_id.isnot(None)
    ).group_by(
        UserActivity.movie_id
    ).order_by(
        desc('views')
    ).limit(limit).all()
    
    return {
        "period_days": period_days,
        "movies": [
            {"movie_id": movie_id, "views": views}
            for movie_id, views in popular
        ]
    }

@app.get("/api/v1/analytics/movies/{movie_id}")
def get_movie_analytics(movie_id: int, db: Session = Depends(get_db)):
    """Получение аналитики конкретного фильма"""
    analytics = db.query(MovieAnalytics).filter(
        MovieAnalytics.movie_id == movie_id
    ).first()
    
    if not analytics:
        raise HTTPException(status_code=404, detail="Movie analytics not found")
    
    return analytics

@app.get("/api/v1/analytics/users/{user_id}/activity")
def get_user_activity(
    user_id: int,
    days: int = 30,
    db: Session = Depends(get_db)
):
    """Получение активности пользователя"""
    since_date = datetime.utcnow() - timedelta(days=days)
    
    activities = db.query(UserActivity).filter(
        UserActivity.user_id == user_id,
        UserActivity.timestamp >= since_date
    ).order_by(desc(UserActivity.timestamp)).limit(100).all()
    
    return {
        "user_id": user_id,
        "period_days": days,
        "activities": [
            {
                "event_type": a.event_type,
                "movie_id": a.movie_id,
                "timestamp": a.timestamp,
                "duration": a.duration_seconds
            }
            for a in activities
        ]
    }

@app.get("/api/v1/analytics/dashboard")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Получение статистики для дашборда"""
    # Общая статистика
    total_users = db.query(func.count(func.distinct(UserActivity.user_id))).scalar()
    total_movies = db.query(func.count(MovieAnalytics.movie_id)).scalar()
    
    # Активность за последние 24 часа
    last_24h = datetime.utcnow() - timedelta(hours=24)
    daily_activity = db.query(func.count(UserActivity.id)).filter(
        UserActivity.timestamp >= last_24h
    ).scalar()
    
    # Самые популярные жанры (нужно расширить модель для этого)
    
    return {
        "total_users": total_users or 0,
        "total_movies": total_movies or 0,
        "daily_activity": daily_activity or 0,
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}