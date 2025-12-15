"""
CRUD операции для Catalog Service.
"""

import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc, asc, func, not_
from sqlalchemy.sql import text

from . import models, schemas
from src.config.settings import settings
from src.shared.exceptions import (
    NotFoundError, ConflictError, ValidationError, 
    AuthorizationError, DatabaseError
)
from src.shared.kafka_producer import send_kafka_message
from src.monitoring.metrics import record_database_query, record_user_event
from src.monitoring.logging_config import request_logger

logger = logging.getLogger(__name__)


# ====== Вспомогательные функции ======

def _get_movie_query(db: Session, include_inactive: bool = False):
    """Базовый запрос для фильмов."""
    query = db.query(models.Movie)
    if not include_inactive:
        query = query.filter(models.Movie.is_active == True)
    return query


def _get_person_query(db: Session, include_inactive: bool = False):
    """Базовый запрос для людей."""
    query = db.query(models.Person)
    if not include_inactive:
        query = query.filter(models.Person.is_active == True)
    return query


def _get_genre_query(db: Session, include_inactive: bool = False):
    """Базовый запрос для жанров."""
    query = db.query(models.Genre)
    if not include_inactive:
        query = query.filter(models.Genre.is_active == True)
    return query


def _send_movie_index_event(movie: models.Movie, action: str = "index"):
    """Отправка события индексации фильма."""
    try:
        event_data = {
            "action": action,
            "movie_id": str(movie.id),
            "title": movie.title,
            "original_title": movie.original_title,
            "description": movie.description,
            "release_year": movie.release_year,
            "rating": movie.rating,
            "age_rating": movie.age_rating.value,
            "country": movie.country,
            "language": movie.language,
            "content_type": movie.content_type.value,
            "genres": [{"id": g.id, "name": g.name, "slug": g.slug} for g in movie.genres],
            "actors": [{"id": str(a.id), "full_name": a.full_name} for a in movie.actors],
            "directors": [{"id": str(d.id), "full_name": d.full_name} for d in movie.directors],
            "created_at": movie.created_at.isoformat(),
            "updated_at": movie.updated_at.isoformat() if movie.updated_at else None
        }
        
        send_kafka_message(
            topic=settings.KAFKA_TOPIC_MOVIE_INDEX,
            value=event_data,
            key=str(movie.id)
        )
        
        logger.debug(f"Movie index event sent: {movie.id} ({action})")
        
    except Exception as e:
        logger.error(f"Failed to send movie index event: {e}")


def _send_user_activity_event(user_id: UUID, activity_type: str, details: Dict[str, Any] = None):
    """Отправка события пользовательской активности."""
    try:
        event_data = {
            "user_id": str(user_id),
            "activity_type": activity_type,
            "timestamp": datetime.utcnow().isoformat(),
            "service": "catalog-service",
            "details": details or {}
        }
        
        send_kafka_message(
            topic=settings.KAFKA_TOPIC_USER_ACTIVITY,
            value=event_data,
            key=str(user_id)
        )
        
        record_user_event(activity_type, "user")
        
    except Exception as e:
        logger.error(f"Failed to send user activity event: {e}")


# ====== CRUD операции для фильмов ======

def get_movie(db: Session, movie_id: UUID, include_inactive: bool = False) -> Optional[models.Movie]:
    """Получение фильма по ID."""
    start_time = datetime.now()
    
    try:
        query = _get_movie_query(db, include_inactive)
        movie = query.filter(models.Movie.id == movie_id).first()
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "movies", duration, movie is not None)
        
        return movie
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "movies", duration, False)
        logger.error(f"Error getting movie {movie_id}: {e}")
        raise DatabaseError(f"Failed to get movie: {str(e)}")


def get_movies(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    filters: Optional[Dict[str, Any]] = None,
    include_inactive: bool = False
) -> List[models.Movie]:
    """Получение списка фильмов с фильтрацией."""
    start_time = datetime.now()
    
    try:
        query = _get_movie_query(db, include_inactive)
        
        if filters:
            # Фильтр по жанрам
            if "genre_ids" in filters and filters["genre_ids"]:
                # Фильтр по нескольким жанрам (AND)
                for genre_id in filters["genre_ids"]:
                    query = query.filter(models.Movie.genres.any(id=genre_id))
            
            # Фильтр по типу контента
            if "content_type" in filters:
                query = query.filter(models.Movie.content_type == filters["content_type"])
            
            # Фильтр по рейтингу
            if "min_rating" in filters:
                query = query.filter(models.Movie.rating >= filters["min_rating"])
            if "max_rating" in filters:
                query = query.filter(models.Movie.rating <= filters["max_rating"])
            
            # Фильтр по году
            if "year_from" in filters:
                query = query.filter(models.Movie.release_year >= filters["year_from"])
            if "year_to" in filters:
                query = query.filter(models.Movie.release_year <= filters["year_to"])
            
            # Фильтр по стране
            if "country" in filters:
                query = query.filter(models.Movie.country == filters["country"])
            
            # Фильтр по языку
            if "language" in filters:
                query = query.filter(models.Movie.language == filters["language"])
            
            # Фильтр по возрастному рейтингу
            if "age_rating" in filters:
                query = query.filter(models.Movie.age_rating == filters["age_rating"])
        
        # Сортировка
        sort_by = filters.get("sort_by") if filters else None
        sort_order = filters.get("sort_order", "desc") if filters else "desc"
        
        if sort_by == "title":
            query = query.order_by(asc(models.Movie.title) if sort_order == "asc" else desc(models.Movie.title))
        elif sort_by == "rating":
            query = query.order_by(asc(models.Movie.rating) if sort_order == "asc" else desc(models.Movie.rating))
        elif sort_by == "release_year":
            query = query.order_by(asc(models.Movie.release_year) if sort_order == "asc" else desc(models.Movie.release_year))
        else:
            query = query.order_by(desc(models.Movie.created_at))
        
        movies = query.offset(skip).limit(limit).all()
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "movies", duration, True)
        
        return movies
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "movies", duration, False)
        logger.error(f"Error getting movies: {e}")
        raise DatabaseError(f"Failed to get movies: {str(e)}")


def search_movies(
    db: Session,
    query_text: str,
    skip: int = 0,
    limit: int = 50,
    filters: Optional[Dict[str, Any]] = None
) -> List[models.Movie]:
    """Поиск фильмов по тексту."""
    start_time = datetime.now()
    
    try:
        search_query = _get_movie_query(db)
        
        # Текстовый поиск
        if query_text:
            search_term = f"%{query_text}%"
            search_query = search_query.filter(
                or_(
                    models.Movie.title.ilike(search_term),
                    models.Movie.original_title.ilike(search_term),
                    models.Movie.description.ilike(search_term)
                )
            )
        
        # Применяем дополнительные фильтры
        if filters:
            if "genre_ids" in filters and filters["genre_ids"]:
                for genre_id in filters["genre_ids"]:
                    search_query = search_query.filter(models.Movie.genres.any(id=genre_id))
            
            if "content_type" in filters:
                search_query = search_query.filter(models.Movie.content_type == filters["content_type"])
            
            if "min_rating" in filters:
                search_query = search_query.filter(models.Movie.rating >= filters["min_rating"])
        
        # Сортировка по релевантности (простейшая реализация)
        search_query = search_query.order_by(
            desc(models.Movie.rating),
            desc(models.Movie.release_year)
        )
        
        movies = search_query.offset(skip).limit(limit).all()
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "movies", duration, True)
        
        return movies
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "movies", duration, False)
        logger.error(f"Error searching movies: {e}")
        raise DatabaseError(f"Failed to search movies: {str(e)}")


def count_movies(db: Session, filters: Optional[Dict[str, Any]] = None) -> int:
    """Подсчет количества фильмов."""
    start_time = datetime.now()
    
    try:
        query = db.query(func.count(models.Movie.id)).filter(models.Movie.is_active == True)
        
        if filters:
            if "genre_ids" in filters and filters["genre_ids"]:
                for genre_id in filters["genre_ids"]:
                    query = query.filter(models.Movie.genres.any(id=genre_id))
            
            if "content_type" in filters:
                query = query.filter(models.Movie.content_type == filters["content_type"])
        
        count = query.scalar()
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("count", "movies", duration, True)
        
        return count
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("count", "movies", duration, False)
        logger.error(f"Error counting movies: {e}")
        raise DatabaseError(f"Failed to count movies: {str(e)}")


def create_movie(db: Session, movie: schemas.MovieCreate, user_id: UUID = None) -> models.Movie:
    """Создание нового фильма."""
    start_time = datetime.now()
    
    try:
        # Проверка уникальности названия
        existing_movie = db.query(models.Movie).filter(
            models.Movie.title == movie.title,
            models.Movie.release_year == movie.release_year
        ).first()
        
        if existing_movie:
            raise ConflictError(f"Movie '{movie.title}' ({movie.release_year}) already exists")
        
        # Создание фильма
        db_movie = models.Movie(
            id=uuid4(),
            title=movie.title,
            original_title=movie.original_title,
            description=movie.description,
            content_type=movie.content_type,
            release_year=movie.release_year,
            duration_minutes=movie.duration_minutes,
            age_rating=movie.age_rating,
            poster_url=movie.poster_url,
            backdrop_url=movie.backdrop_url,
            trailer_url=movie.trailer_url,
            country=movie.country,
            language=movie.language,
            subtitles=movie.subtitles,
            metadata=movie.metadata or {}
        )
        
        # Добавление жанров
        if movie.genre_ids:
            genres = db.query(models.Genre).filter(models.Genre.id.in_(movie.genre_ids)).all()
            db_movie.genres = genres
        
        # Добавление актеров
        if movie.actor_ids:
            actors = db.query(models.Person).filter(models.Person.id.in_(movie.actor_ids)).all()
            db_movie.actors = actors
        
        # Добавление режиссеров
        if movie.director_ids:
            directors = db.query(models.Person).filter(models.Person.id.in_(movie.director_ids)).all()
            db_movie.directors = directors
        
        # Добавление сценаристов
        if movie.writer_ids:
            writers = db.query(models.Person).filter(models.Person.id.in_(movie.writer_ids)).all()
            db_movie.writers = writers
        
        db.add(db_movie)
        db.commit()
        db.refresh(db_movie)
        
        # Отправка события индексации
        _send_movie_index_event(db_movie, "index")
        
        # Логирование аудита
        if user_id:
            request_logger.log_audit(
                action="movie_created",
                user_id=str(user_id),
                resource_type="movie",
                resource_id=str(db_movie.id),
                details={"title": db_movie.title}
            )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "movies", duration, True)
        
        logger.info(f"Movie created: {db_movie.title} ({db_movie.id})")
        return db_movie
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "movies", duration, False)
        
        if not isinstance(e, (ConflictError, ValidationError)):
            logger.error(f"Error creating movie: {e}")
            raise DatabaseError(f"Failed to create movie: {str(e)}")
        raise


def update_movie(
    db: Session,
    movie_id: UUID,
    movie_update: schemas.MovieUpdate,
    user_id: UUID = None
) -> models.Movie:
    """Обновление фильма."""
    start_time = datetime.now()
    
    try:
        db_movie = get_movie(db, movie_id, include_inactive=True)
        if not db_movie:
            raise NotFoundError("movie", movie_id)
        
        # Обновление полей
        update_data = movie_update.dict(exclude_unset=True, exclude={"genre_ids", "actor_ids", "director_ids", "writer_ids"})
        
        for field, value in update_data.items():
            if value is not None:
                setattr(db_movie, field, value)
        
        # Обновление связей если указаны
        if movie_update.genre_ids is not None:
            genres = db.query(models.Genre).filter(models.Genre.id.in_(movie_update.genre_ids)).all()
            db_movie.genres = genres
        
        if movie_update.actor_ids is not None:
            actors = db.query(models.Person).filter(models.Person.id.in_(movie_update.actor_ids)).all()
            db_movie.actors = actors
        
        if movie_update.director_ids is not None:
            directors = db.query(models.Person).filter(models.Person.id.in_(movie_update.director_ids)).all()
            db_movie.directors = directors
        
        if movie_update.writer_ids is not None:
            writers = db.query(models.Person).filter(models.Person.id.in_(movie_update.writer_ids)).all()
            db_movie.writers = writers
        
        db_movie.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_movie)
        
        # Отправка события обновления
        _send_movie_index_event(db_movie, "update")
        
        # Логирование аудита
        if user_id:
            request_logger.log_audit(
                action="movie_updated",
                user_id=str(user_id),
                resource_type="movie",
                resource_id=str(db_movie.id),
                details={"updated_fields": list(update_data.keys())}
            )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "movies", duration, True)
        
        logger.info(f"Movie updated: {db_movie.id}")
        return db_movie
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "movies", duration, False)
        
        if isinstance(e, NotFoundError):
            raise
        logger.error(f"Error updating movie {movie_id}: {e}")
        raise DatabaseError(f"Failed to update movie: {str(e)}")


def delete_movie(db: Session, movie_id: UUID, user_id: UUID = None) -> bool:
    """Мягкое удаление фильма."""
    start_time = datetime.now()
    
    try:
        db_movie = get_movie(db, movie_id, include_inactive=True)
        if not db_movie:
            raise NotFoundError("movie", movie_id)
        
        # Мягкое удаление
        db_movie.is_active = False
        db_movie.updated_at = datetime.utcnow()
        db.commit()
        
        # Отправка события удаления
        _send_movie_index_event(db_movie, "delete")
        
        # Логирование аудита
        if user_id:
            request_logger.log_audit(
                action="movie_deleted",
                user_id=str(user_id),
                resource_type="movie",
                resource_id=str(db_movie.id),
                details={"title": db_movie.title}
            )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "movies", duration, True)
        
        logger.info(f"Movie deleted (soft): {movie_id}")
        return True
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "movies", duration, False)
        
        if isinstance(e, NotFoundError):
            raise
        logger.error(f"Error deleting movie {movie_id}: {e}")
        raise DatabaseError(f"Failed to delete movie: {str(e)}")


def get_popular_movies(db: Session, limit: int = 10, days: int = 30) -> List[models.Movie]:
    """Получение популярных фильмов (заглушка - в реальном приложении учитывались бы просмотры)."""
    start_time = datetime.now()
    
    try:
        query = _get_movie_query(db)
        
        # Простая реализация: фильмы с высоким рейтингом
        movies = query.order_by(
            desc(models.Movie.rating),
            desc(models.Movie.created_at)
        ).limit(limit).all()
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "movies", duration, True)
        
        return movies
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "movies", duration, False)
        logger.error(f"Error getting popular movies: {e}")
        raise DatabaseError(f"Failed to get popular movies: {str(e)}")


def get_recommended_movies(
    db: Session,
    user_id: UUID,
    limit: int = 10
) -> List[models.Movie]:
    """Получение рекомендованных фильмов (заглушка)."""
    start_time = datetime.now()
    
    try:
        # Простая реализация: возвращаем новые фильмы
        query = _get_movie_query(db)
        movies = query.order_by(desc(models.Movie.created_at)).limit(limit).all()
        
        # Отправляем событие активности
        _send_user_activity_event(
            user_id=user_id,
            activity_type="get_recommendations",
            details={"count": len(movies)}
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "movies", duration, True)
        
        return movies
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "movies", duration, False)
        logger.error(f"Error getting recommended movies: {e}")
        raise DatabaseError(f"Failed to get recommended movies: {str(e)}")


# ====== CRUD операции для жанров ======

def get_genre(db: Session, genre_id: int, include_inactive: bool = False) -> Optional[models.Genre]:
    """Получение жанра по ID."""
    start_time = datetime.now()
    
    try:
        query = _get_genre_query(db, include_inactive)
        genre = query.filter(models.Genre.id == genre_id).first()
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "genres", duration, genre is not None)
        
        return genre
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "genres", duration, False)
        logger.error(f"Error getting genre {genre_id}: {e}")
        raise DatabaseError(f"Failed to get genre: {str(e)}")


def get_genre_by_slug(db: Session, slug: str, include_inactive: bool = False) -> Optional[models.Genre]:
    """Получение жанра по slug."""
    start_time = datetime.now()
    
    try:
        query = _get_genre_query(db, include_inactive)
        genre = query.filter(models.Genre.slug == slug).first()
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "genres", duration, genre is not None)
        
        return genre
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "genres", duration, False)
        logger.error(f"Error getting genre by slug {slug}: {e}")
        raise DatabaseError(f"Failed to get genre: {str(e)}")


def get_genres(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    filters: Optional[Dict[str, Any]] = None,
    include_inactive: bool = False
) -> List[models.Genre]:
    """Получение списка жанров."""
    start_time = datetime.now()
    
    try:
        query = _get_genre_query(db, include_inactive)
        
        if filters and "is_active" in filters:
            query = query.filter(models.Genre.is_active == filters["is_active"])
        
        genres = query.order_by(models.Genre.name).offset(skip).limit(limit).all()
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "genres", duration, True)
        
        return genres
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "genres", duration, False)
        logger.error(f"Error getting genres: {e}")
        raise DatabaseError(f"Failed to get genres: {str(e)}")


def create_genre(db: Session, genre: schemas.GenreCreate, user_id: UUID = None) -> models.Genre:
    """Создание нового жанра."""
    start_time = datetime.now()
    
    try:
        # Проверка уникальности
        existing_genre = db.query(models.Genre).filter(
            or_(
                models.Genre.name == genre.name,
                models.Genre.slug == genre.slug
            )
        ).first()
        
        if existing_genre:
            raise ConflictError(f"Genre with name '{genre.name}' or slug '{genre.slug}' already exists")
        
        db_genre = models.Genre(
            name=genre.name,
            slug=genre.slug,
            description=genre.description,
            icon_url=genre.icon_url
        )
        
        db.add(db_genre)
        db.commit()
        db.refresh(db_genre)
        
        # Логирование аудита
        if user_id:
            request_logger.log_audit(
                action="genre_created",
                user_id=str(user_id),
                resource_type="genre",
                resource_id=str(db_genre.id),
                details={"name": db_genre.name}
            )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "genres", duration, True)
        
        logger.info(f"Genre created: {db_genre.name} ({db_genre.id})")
        return db_genre
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "genres", duration, False)
        
        if not isinstance(e, (ConflictError, ValidationError)):
            logger.error(f"Error creating genre: {e}")
            raise DatabaseError(f"Failed to create genre: {str(e)}")
        raise


def update_genre(
    db: Session,
    genre_id: int,
    genre_update: schemas.GenreUpdate,
    user_id: UUID = None
) -> models.Genre:
    """Обновление жанра."""
    start_time = datetime.now()
    
    try:
        db_genre = get_genre(db, genre_id, include_inactive=True)
        if not db_genre:
            raise NotFoundError("genre", genre_id)
        
        # Проверка уникальности при обновлении
        if genre_update.name:
            existing_genre = db.query(models.Genre).filter(
                models.Genre.name == genre_update.name,
                models.Genre.id != genre_id
            ).first()
            if existing_genre:
                raise ConflictError(f"Genre with name '{genre_update.name}' already exists")
        
        # Обновление полей
        update_data = genre_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(db_genre, field, value)
        
        db.commit()
        db.refresh(db_genre)
        
        # Логирование аудита
        if user_id:
            request_logger.log_audit(
                action="genre_updated",
                user_id=str(user_id),
                resource_type="genre",
                resource_id=str(db_genre.id),
                details={"updated_fields": list(update_data.keys())}
            )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "genres", duration, True)
        
        logger.info(f"Genre updated: {genre_id}")
        return db_genre
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "genres", duration, False)
        
        if isinstance(e, NotFoundError):
            raise
        logger.error(f"Error updating genre {genre_id}: {e}")
        raise DatabaseError(f"Failed to update genre: {str(e)}")


# ====== CRUD операции для людей ======

def get_person(db: Session, person_id: UUID, include_inactive: bool = False) -> Optional[models.Person]:
    """Получение человека по ID."""
    start_time = datetime.now()
    
    try:
        query = _get_person_query(db, include_inactive)
        person = query.filter(models.Person.id == person_id).first()
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "persons", duration, person is not None)
        
        return person
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "persons", duration, False)
        logger.error(f"Error getting person {person_id}: {e}")
        raise DatabaseError(f"Failed to get person: {str(e)}")


def get_persons(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    filters: Optional[Dict[str, Any]] = None,
    include_inactive: bool = False
) -> List[models.Person]:
    """Получение списка людей."""
    start_time = datetime.now()
    
    try:
        query = _get_person_query(db, include_inactive)
        
        if filters:
            if "query" in filters and filters["query"]:
                search_term = f"%{filters['query']}%"
                query = query.filter(models.Person.full_name.ilike(search_term))
            
            if "role" in filters:
                if filters["role"] == "actor":
                    query = query.filter(models.Person.acted_in.any())
                elif filters["role"] == "director":
                    query = query.filter(models.Person.directed.any())
                elif filters["role"] == "writer":
                    query = query.filter(models.Person.wrote.any())
        
        persons = query.order_by(models.Person.full_name).offset(skip).limit(limit).all()
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "persons", duration, True)
        
        return persons
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "persons", duration, False)
        logger.error(f"Error getting persons: {e}")
        raise DatabaseError(f"Failed to get persons: {str(e)}")


def create_person(db: Session, person: schemas.PersonCreate, user_id: UUID = None) -> models.Person:
    """Создание нового человека."""
    start_time = datetime.now()
    
    try:
        # Проверка существования по IMDb ID
        if person.imdb_id:
            existing_person = db.query(models.Person).filter(
                models.Person.imdb_id == person.imdb_id
            ).first()
            if existing_person:
                raise ConflictError(f"Person with IMDb ID '{person.imdb_id}' already exists")
        
        db_person = models.Person(
            id=uuid4(),
            full_name=person.full_name,
            birth_date=person.birth_date,
            birth_place=person.birth_place,
            death_date=person.death_date,
            biography=person.biography,
            photo_url=person.photo_url,
            imdb_id=person.imdb_id
        )
        
        db.add(db_person)
        db.commit()
        db.refresh(db_person)
        
        # Логирование аудита
        if user_id:
            request_logger.log_audit(
                action="person_created",
                user_id=str(user_id),
                resource_type="person",
                resource_id=str(db_person.id),
                details={"full_name": db_person.full_name}
            )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "persons", duration, True)
        
        logger.info(f"Person created: {db_person.full_name} ({db_person.id})")
        return db_person
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "persons", duration, False)
        
        if not isinstance(e, (ConflictError, ValidationError)):
            logger.error(f"Error creating person: {e}")
            raise DatabaseError(f"Failed to create person: {str(e)}")
        raise


def update_person(
    db: Session,
    person_id: UUID,
    person_update: schemas.PersonUpdate,
    user_id: UUID = None
) -> models.Person:
    """Обновление человека."""
    start_time = datetime.now()
    
    try:
        db_person = get_person(db, person_id, include_inactive=True)
        if not db_person:
            raise NotFoundError("person", person_id)
        
        # Проверка уникальности IMDb ID
        if person_update.imdb_id and person_update.imdb_id != db_person.imdb_id:
            existing_person = db.query(models.Person).filter(
                models.Person.imdb_id == person_update.imdb_id,
                models.Person.id != person_id
            ).first()
            if existing_person:
                raise ConflictError(f"Person with IMDb ID '{person_update.imdb_id}' already exists")
        
        # Обновление полей
        update_data = person_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(db_person, field, value)
        
        db_person.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_person)
        
        # Логирование аудита
        if user_id:
            request_logger.log_audit(
                action="person_updated",
                user_id=str(user_id),
                resource_type="person",
                resource_id=str(db_person.id),
                details={"updated_fields": list(update_data.keys())}
            )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "persons", duration, True)
        
        logger.info(f"Person updated: {person_id}")
        return db_person
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("update", "persons", duration, False)
        
        if isinstance(e, NotFoundError):
            raise
        logger.error(f"Error updating person {person_id}: {e}")
        raise DatabaseError(f"Failed to update person: {str(e)}")


# ====== CRUD операции для сезонов и серий ======

def get_season(db: Session, season_id: UUID) -> Optional[models.Season]:
    """Получение сезона по ID."""
    start_time = datetime.now()
    
    try:
        season = db.query(models.Season).filter(models.Season.id == season_id).first()
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "seasons", duration, season is not None)
        
        return season
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "seasons", duration, False)
        logger.error(f"Error getting season {season_id}: {e}")
        raise DatabaseError(f"Failed to get season: {str(e)}")


def create_season(
    db: Session,
    movie_id: UUID,
    season: schemas.SeasonCreate,
    user_id: UUID = None
) -> models.Season:
    """Создание нового сезона."""
    start_time = datetime.now()
    
    try:
        # Проверка существования фильма
        movie = get_movie(db, movie_id)
        if not movie:
            raise NotFoundError("movie", movie_id)
        
        # Проверка уникальности номера сезона для этого фильма
        existing_season = db.query(models.Season).filter(
            models.Season.movie_id == movie_id,
            models.Season.season_number == season.season_number
        ).first()
        
        if existing_season:
            raise ConflictError(f"Season {season.season_number} already exists for movie {movie_id}")
        
        db_season = models.Season(
            id=uuid4(),
            movie_id=movie_id,
            season_number=season.season_number,
            title=season.title,
            description=season.description,
            episode_count=season.episode_count or 0,
            release_year=season.release_year,
            poster_url=season.poster_url
        )
        
        db.add(db_season)
        db.commit()
        db.refresh(db_season)
        
        # Логирование аудита
        if user_id:
            request_logger.log_audit(
                action="season_created",
                user_id=str(user_id),
                resource_type="season",
                resource_id=str(db_season.id),
                details={
                    "movie_id": str(movie_id),
                    "season_number": season.season_number
                }
            )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "seasons", duration, True)
        
        logger.info(f"Season created: {season.season_number} for movie {movie_id}")
        return db_season
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "seasons", duration, False)
        
        if not isinstance(e, (NotFoundError, ConflictError, ValidationError)):
            logger.error(f"Error creating season: {e}")
            raise DatabaseError(f"Failed to create season: {str(e)}")
        raise


def create_episode(
    db: Session,
    season_id: UUID,
    episode: schemas.EpisodeCreate,
    user_id: UUID = None
) -> models.Episode:
    """Создание новой серии."""
    start_time = datetime.now()
    
    try:
        # Проверка существования сезона
        season = get_season(db, season_id)
        if not season:
            raise NotFoundError("season", season_id)
        
        # Проверка уникальности номера серии для этого сезона
        existing_episode = db.query(models.Episode).filter(
            models.Episode.season_id == season_id,
            models.Episode.episode_number == episode.episode_number
        ).first()
        
        if existing_episode:
            raise ConflictError(f"Episode {episode.episode_number} already exists for season {season_id}")
        
        db_episode = models.Episode(
            id=uuid4(),
            season_id=season_id,
            episode_number=episode.episode_number,
            title=episode.title,
            description=episode.description,
            duration_minutes=episode.duration_minutes,
            video_url=episode.video_url,
            release_date=episode.release_date
        )
        
        db.add(db_episode)
        db.commit()
        db.refresh(db_episode)
        
        # Обновление счетчика серий в сезоне
        season.episode_count = db.query(models.Episode).filter(
            models.Episode.season_id == season_id
        ).count()
        db.commit()
        
        # Логирование аудита
        if user_id:
            request_logger.log_audit(
                action="episode_created",
                user_id=str(user_id),
                resource_type="episode",
                resource_id=str(db_episode.id),
                details={
                    "season_id": str(season_id),
                    "episode_number": episode.episode_number
                }
            )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "episodes", duration, True)
        
        logger.info(f"Episode created: {episode.episode_number} for season {season_id}")
        return db_episode
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "episodes", duration, False)
        
        if not isinstance(e, (NotFoundError, ConflictError, ValidationError)):
            logger.error(f"Error creating episode: {e}")
            raise DatabaseError(f"Failed to create episode: {str(e)}")
        raise


# ====== CRUD операции для отзывов ======

def create_review(
    db: Session,
    review: schemas.ReviewCreate,
    user_id: UUID,
    ip_address: Optional[str] = None
) -> models.Review:
    """Создание нового отзыва."""
    start_time = datetime.now()
    
    try:
        # Проверка существования фильма
        movie = get_movie(db, review.movie_id)
        if not movie:
            raise NotFoundError("movie", review.movie_id)
        
        # Проверка существования отзыва от этого пользователя
        existing_review = db.query(models.Review).filter(
            models.Review.movie_id == review.movie_id,
            models.Review.user_id == user_id
        ).first()
        
        if existing_review:
            raise ConflictError("User has already reviewed this movie")
        
        db_review = models.Review(
            id=uuid4(),
            movie_id=review.movie_id,
            user_id=user_id,
            rating=review.rating,
            title=review.title,
            comment=review.comment
        )
        
        db.add(db_review)
        db.commit()
        db.refresh(db_review)
        
        # Обновление среднего рейтинга фильма
        _update_movie_rating(db, review.movie_id)
        
        # Отправка события активности
        _send_user_activity_event(
            user_id=user_id,
            activity_type="review_created",
            details={
                "movie_id": str(review.movie_id),
                "rating": review.rating,
                "review_id": str(db_review.id)
            }
        )
        
        # Отправка в Kafka для аналитики
        send_kafka_message(
            topic=settings.KAFKA_TOPIC_USER_ACTIVITY,
            value={
                "user_id": str(user_id),
                "activity_type": "review_created",
                "movie_id": str(review.movie_id),
                "rating": review.rating,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "reviews", duration, True)
        
        logger.info(f"Review created by user {user_id} for movie {review.movie_id}")
        return db_review
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "reviews", duration, False)
        
        if not isinstance(e, (NotFoundError, ConflictError, ValidationError)):
            logger.error(f"Error creating review: {e}")
            raise DatabaseError(f"Failed to create review: {str(e)}")
        raise


def _update_movie_rating(db: Session, movie_id: UUID):
    """Обновление среднего рейтинга фильма."""
    try:
        # Вычисляем средний рейтинг
        result = db.query(
            func.count(models.Review.id),
            func.avg(models.Review.rating)
        ).filter(
            models.Review.movie_id == movie_id,
            models.Review.is_active == True
        ).first()
        
        if result and result[0] > 0:
            avg_rating = float(result[1]) if result[1] else 0.0
        else:
            avg_rating = 0.0
        
        # Обновляем фильм
        movie = db.query(models.Movie).filter(models.Movie.id == movie_id).first()
        if movie:
            movie.rating = round(avg_rating, 1)
            db.commit()
            
            # Отправляем событие обновления рейтинга
            _send_movie_index_event(movie, "update")
    
    except Exception as e:
        logger.error(f"Error updating movie rating {movie_id}: {e}")


# ====== CRUD операции для списка просмотра ======

def add_to_watchlist(
    db: Session,
    user_id: UUID,
    watchlist_item: schemas.WatchlistCreate
) -> models.Watchlist:
    """Добавление фильма в список просмотра."""
    start_time = datetime.now()
    
    try:
        # Проверка существования фильма
        movie = get_movie(db, watchlist_item.movie_id)
        if not movie:
            raise NotFoundError("movie", watchlist_item.movie_id)
        
        # Проверка существования записи
        existing_item = db.query(models.Watchlist).filter(
            models.Watchlist.user_id == user_id,
            models.Watchlist.movie_id == watchlist_item.movie_id
        ).first()
        
        if existing_item:
            raise ConflictError("Movie already in watchlist")
        
        db_watchlist = models.Watchlist(
            id=uuid4(),
            user_id=user_id,
            movie_id=watchlist_item.movie_id,
            notes=watchlist_item.notes
        )
        
        db.add(db_watchlist)
        db.commit()
        db.refresh(db_watchlist)
        
        # Отправка события активности
        _send_user_activity_event(
            user_id=user_id,
            activity_type="watchlist_added",
            details={"movie_id": str(watchlist_item.movie_id)}
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "watchlists", duration, True)
        
        logger.info(f"Movie {watchlist_item.movie_id} added to watchlist for user {user_id}")
        return db_watchlist
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("insert", "watchlists", duration, False)
        
        if not isinstance(e, (NotFoundError, ConflictError)):
            logger.error(f"Error adding to watchlist: {e}")
            raise DatabaseError(f"Failed to add to watchlist: {str(e)}")
        raise


def get_watchlist(
    db: Session,
    user_id: UUID,
    skip: int = 0,
    limit: int = 50
) -> List[models.Watchlist]:
    """Получение списка просмотра пользователя."""
    start_time = datetime.now()
    
    try:
        watchlist = db.query(models.Watchlist).filter(
            models.Watchlist.user_id == user_id
        ).order_by(
            desc(models.Watchlist.added_at)
        ).offset(skip).limit(limit).all()
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "watchlists", duration, True)
        
        return watchlist
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "watchlists", duration, False)
        logger.error(f"Error getting watchlist for user {user_id}: {e}")
        raise DatabaseError(f"Failed to get watchlist: {str(e)}")


def remove_from_watchlist(db: Session, user_id: UUID, movie_id: UUID) -> bool:
    """Удаление фильма из списка просмотра."""
    start_time = datetime.now()
    
    try:
        watchlist_item = db.query(models.Watchlist).filter(
            models.Watchlist.user_id == user_id,
            models.Watchlist.movie_id == movie_id
        ).first()
        
        if not watchlist_item:
            raise NotFoundError("watchlist item", f"{user_id}/{movie_id}")
        
        db.delete(watchlist_item)
        db.commit()
        
        # Отправка события активности
        _send_user_activity_event(
            user_id=user_id,
            activity_type="watchlist_removed",
            details={"movie_id": str(movie_id)}
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("delete", "watchlists", duration, True)
        
        logger.info(f"Movie {movie_id} removed from watchlist for user {user_id}")
        return True
        
    except Exception as e:
        db.rollback()
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("delete", "watchlists", duration, False)
        
        if isinstance(e, NotFoundError):
            raise
        logger.error(f"Error removing from watchlist: {e}")
        raise DatabaseError(f"Failed to remove from watchlist: {str(e)}")


# ====== Статистика ======

def get_movie_stats(db: Session, movie_id: UUID) -> Dict[str, Any]:
    """Получение статистики фильма."""
    start_time = datetime.now()
    
    try:
        movie = get_movie(db, movie_id)
        if not movie:
            raise NotFoundError("movie", movie_id)
        
        # Количество отзывов
        review_count = db.query(func.count(models.Review.id)).filter(
            models.Review.movie_id == movie_id,
            models.Review.is_active == True
        ).scalar() or 0
        
        # Количество в списках просмотра
        watchlist_count = db.query(func.count(models.Watchlist.id)).filter(
            models.Watchlist.movie_id == movie_id
        ).scalar() or 0
        
        stats = {
            "movie_id": str(movie_id),
            "title": movie.title,
            "rating": movie.rating,
            "review_count": review_count,
            "watchlist_count": watchlist_count,
            "genre_count": len(movie.genres),
            "actor_count": len(movie.actors),
            "release_year": movie.release_year,
            "last_updated": datetime.utcnow().isoformat()
        }
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "movies", duration, True)
        
        return stats
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "movies", duration, False)
        
        if isinstance(e, NotFoundError):
            raise
        logger.error(f"Error getting movie stats {movie_id}: {e}")
        raise DatabaseError(f"Failed to get movie stats: {str(e)}")


def get_genre_stats(db: Session) -> List[Dict[str, Any]]:
    """Получение статистики по жанрам."""
    start_time = datetime.now()
    
    try:
        # Используем сырой SQL для сложной агрегации
        query = text("""
            SELECT 
                g.id as genre_id,
                g.name as genre_name,
                COUNT(DISTINCT mg.movie_id) as movie_count,
                COALESCE(AVG(m.rating), 0) as average_rating,
                COUNT(DISTINCT r.id) as review_count
            FROM genres g
            LEFT JOIN movie_genre mg ON g.id = mg.genre_id
            LEFT JOIN movies m ON mg.movie_id = m.id AND m.is_active = true
            LEFT JOIN reviews r ON m.id = r.movie_id AND r.is_active = true
            WHERE g.is_active = true
            GROUP BY g.id, g.name
            ORDER BY movie_count DESC
        """)
        
        result = db.execute(query)
        stats = [
            {
                "genre_id": row[0],
                "genre_name": row[1],
                "movie_count": row[2],
                "average_rating": float(row[3]) if row[3] else 0.0,
                "review_count": row[4]
            }
            for row in result
        ]
        
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "genres", duration, True)
        
        return stats
        
    except Exception as e:
        duration = (datetime.now() - start_time).total_seconds()
        record_database_query("select", "genres", duration, False)
        logger.error(f"Error getting genre stats: {e}")
        raise DatabaseError(f"Failed to get genre stats: {str(e)}")