from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, ForeignKey
from sqlalchemy.sql import func
from src.config.database import Base

class UserActivity(Base):
    __tablename__ = "user_activity"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    session_id = Column(String(255), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # watch_start, watch_end, search, etc.
    movie_id = Column(Integer, nullable=True, index=True)
    search_query = Column(String(255), nullable=True)
    device_type = Column(String(50))  # web, mobile, tv
    platform = Column(String(50))  # windows, ios, android
    location = Column(String(255))
    duration_seconds = Column(Float, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    metadata = Column(JSON)  # Дополнительные данные

class WatchHistory(Base):
    __tablename__ = "watch_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    movie_id = Column(Integer, nullable=False, index=True)
    watch_date = Column(DateTime(timezone=True), server_default=func.now())
    duration_watched = Column(Integer)  # в секундах
    total_duration = Column(Integer)  # общая длительность фильма
    completed = Column(Integer, default=0)  # 0 - нет, 1 - да
    last_position = Column(Integer)  # последняя позиция просмотра

class MovieAnalytics(Base):
    __tablename__ = "movie_analytics"
    
    movie_id = Column(Integer, primary_key=True, index=True)
    total_views = Column(Integer, default=0)
    total_watch_time = Column(Integer, default=0)  # в секундах
    average_watch_percentage = Column(Float, default=0.0)
    completion_rate = Column(Float, default=0.0)
    average_rating = Column(Float, default=0.0)
    total_ratings = Column(Integer, default=0)
    last_updated = Column(DateTime(timezone=True), onupdate=func.now())

class UserPreferences(Base):
    __tablename__ = "user_preferences"
    
    user_id = Column(Integer, primary_key=True, index=True)
    favorite_genres = Column(JSON, default=list)
    favorite_actors = Column(JSON, default=list)
    watched_movies = Column(JSON, default=list)  # список ID просмотренных фильмов
    watch_time_by_genre = Column(JSON, default=dict)  # {"action": 3600, "comedy": 1800}
    last_updated = Column(DateTime(timezone=True), onupdate=func.now())