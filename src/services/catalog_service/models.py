"""
Модели базы данных для Catalog Service.
"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, Boolean,
    ForeignKey, Table, Enum, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from enum import Enum as PyEnum
import uuid
from src.config.database import Base


# ====== Enums ======

class ContentType(PyEnum):
    """Типы контента."""
    MOVIE = "movie"
    SERIES = "series"
    DOCUMENTARY = "documentary"
    SHORT = "short"
    ANIMATION = "animation"


class AgeRating(PyEnum):
    """Возрастные рейтинги."""
    G = "G"        # Для всех возрастов
    PG = "PG"      # Родительский контроль
    PG13 = "PG-13" # Детям до 13 с родителями
    R = "R"        # Ограничение 17+
    NC17 = "NC-17" # Только для взрослых


# ====== Association tables ======

movie_genre_association = Table(
    'movie_genre',
    Base.metadata,
    Column('movie_id', UUID(as_uuid=True), ForeignKey('movies.id')),
    Column('genre_id', Integer, ForeignKey('genres.id')),
    Column('created_at', DateTime(timezone=True), server_default=func.now())
)

movie_actor_association = Table(
    'movie_actor',
    Base.metadata,
    Column('movie_id', UUID(as_uuid=True), ForeignKey('movies.id')),
    Column('person_id', UUID(as_uuid=True), ForeignKey('persons.id')),
    Column('role_name', String(255)),  # Название роли
    Column('is_lead', Boolean, default=False),  # Главная роль
    Column('created_at', DateTime(timezone=True), server_default=func.now())
)

movie_director_association = Table(
    'movie_director',
    Base.metadata,
    Column('movie_id', UUID(as_uuid=True), ForeignKey('movies.id')),
    Column('person_id', UUID(as_uuid=True), ForeignKey('persons.id')),
    Column('created_at', DateTime(timezone=True), server_default=func.now())
)

movie_writer_association = Table(
    'movie_writer',
    Base.metadata,
    Column('movie_id', UUID(as_uuid=True), ForeignKey('movies.id')),
    Column('person_id', UUID(as_uuid=True), ForeignKey('persons.id')),
    Column('created_at', DateTime(timezone=True), server_default=func.now())
)


# ====== Main models ======

class Movie(Base):
    """
    Модель фильма/сериала.
    
    Attributes:
        id: UUID фильма
        title: Название на русском
        original_title: Оригинальное название
        description: Описание
        content_type: Тип контента
        release_year: Год выпуска
        duration_minutes: Длительность в минутах
        rating: Рейтинг (0-10)
        age_rating: Возрастной рейтинг
        poster_url: URL постера
        backdrop_url: URL фонового изображения
        trailer_url: URL трейлера
        video_url: URL видео файла (для стриминга)
        country: Страна производства
        language: Язык оригинала
        subtitles: Доступные субтитры (JSON)
        is_active: Активен ли фильм
        metadata: Дополнительные метаданные (JSON)
        created_at: Дата создания
        updated_at: Дата обновления
    """
    
    __tablename__ = "movies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    title = Column(String(255), nullable=False, index=True)
    original_title = Column(String(255), index=True)
    description = Column(Text)
    
    content_type = Column(
        Enum(ContentType),
        default=ContentType.MOVIE,
        nullable=False,
        index=True
    )
    
    release_year = Column(Integer, index=True)
    duration_minutes = Column(Integer)  # Для сериалов - средняя длительность серии
    
    rating = Column(Float, default=0.0)  # Средний рейтинг
    age_rating = Column(Enum(AgeRating), default=AgeRating.PG13, index=True)
    
    poster_url = Column(String(500))
    backdrop_url = Column(String(500))
    trailer_url = Column(String(500))
    video_url = Column(String(500))  # Основной видео файл
    
    country = Column(String(100), index=True)
    language = Column(String(50), index=True)
    subtitles = Column(JSONB, default=[])  # Список доступных языков субтитров
    
    is_active = Column(Boolean, default=True, index=True)
    metadata = Column(JSONB, default={})  # Дополнительные метаданные
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    genres = relationship("Genre", secondary=movie_genre_association, back_populates="movies")
    actors = relationship("Person", secondary=movie_actor_association, back_populates="acted_in")
    directors = relationship("Person", secondary=movie_director_association, back_populates="directed")
    writers = relationship("Person", secondary=movie_writer_association, back_populates="wrote")
    seasons = relationship("Season", back_populates="movie", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="movie", cascade="all, delete-orphan")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": str(self.id),
            "title": self.title,
            "original_title": self.original_title,
            "description": self.description,
            "content_type": self.content_type.value,
            "release_year": self.release_year,
            "duration_minutes": self.duration_minutes,
            "rating": self.rating,
            "age_rating": self.age_rating.value,
            "poster_url": self.poster_url,
            "backdrop_url": self.backdrop_url,
            "trailer_url": self.trailer_url,
            "video_url": self.video_url,
            "country": self.country,
            "language": self.language,
            "subtitles": self.subtitles,
            "is_active": self.is_active,
            "genres": [{"id": g.id, "name": g.name, "slug": g.slug} for g in self.genres],
            "actors": [p.to_dict() for p in self.actors],
            "directors": [p.to_dict() for p in self.directors],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class Season(Base):
    """
    Модель сезона сериала.
    
    Attributes:
        id: UUID сезона
        movie_id: ID фильма (сериала)
        season_number: Номер сезона
        title: Название сезона
        description: Описание сезона
        episode_count: Количество серий
        release_year: Год выпуска
        poster_url: URL постера сезона
        created_at: Дата создания
        updated_at: Дата обновления
    """
    
    __tablename__ = "seasons"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    movie_id = Column(UUID(as_uuid=True), ForeignKey('movies.id'), nullable=False, index=True)
    season_number = Column(Integer, nullable=False)
    title = Column(String(255))
    description = Column(Text)
    episode_count = Column(Integer, default=0)
    release_year = Column(Integer)
    poster_url = Column(String(500))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    movie = relationship("Movie", back_populates="seasons")
    episodes = relationship("Episode", back_populates="season", cascade="all, delete-orphan")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": str(self.id),
            "movie_id": str(self.movie_id),
            "season_number": self.season_number,
            "title": self.title,
            "description": self.description,
            "episode_count": self.episode_count,
            "release_year": self.release_year,
            "poster_url": self.poster_url,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "episodes": [e.to_dict() for e in self.episodes]
        }


class Episode(Base):
    """
    Модель серии сериала.
    
    Attributes:
        id: UUID серии
        season_id: ID сезона
        episode_number: Номер серии
        title: Название серии
        description: Описание серии
        duration_minutes: Длительность в минутах
        video_url: URL видео файла
        release_date: Дата выпуска
        created_at: Дата создания
        updated_at: Дата обновления
    """
    
    __tablename__ = "episodes"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    season_id = Column(UUID(as_uuid=True), ForeignKey('seasons.id'), nullable=False, index=True)
    episode_number = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    duration_minutes = Column(Integer)
    video_url = Column(String(500))
    release_date = Column(DateTime(timezone=True))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    season = relationship("Season", back_populates="episodes")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": str(self.id),
            "season_id": str(self.season_id),
            "episode_number": self.episode_number,
            "title": self.title,
            "description": self.description,
            "duration_minutes": self.duration_minutes,
            "video_url": self.video_url,
            "release_date": self.release_date.isoformat() if self.release_date else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class Genre(Base):
    """
    Модель жанра.
    
    Attributes:
        id: ID жанра
        name: Название жанра
        slug: Уникальный идентификатор
        description: Описание жанра
        icon_url: URL иконки
        is_active: Активен ли жанр
        created_at: Дата создания
    """
    
    __tablename__ = "genres"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False, index=True)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(Text)
    icon_url = Column(String(500))
    is_active = Column(Boolean, default=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    movies = relationship("Movie", secondary=movie_genre_association, back_populates="genres")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "description": self.description,
            "icon_url": self.icon_url,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat()
        }


class Person(Base):
    """
    Модель человека (актер, режиссер, сценарист).
    
    Attributes:
        id: UUID человека
        full_name: Полное имя
        birth_date: Дата рождения
        birth_place: Место рождения
        death_date: Дата смерти
        biography: Биография
        photo_url: URL фотографии
        imdb_id: ID на IMDb
        is_active: Активен ли
        metadata: Дополнительные метаданные
        created_at: Дата создания
        updated_at: Дата обновления
    """
    
    __tablename__ = "persons"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    full_name = Column(String(255), nullable=False, index=True)
    birth_date = Column(DateTime(timezone=True))
    birth_place = Column(String(255))
    death_date = Column(DateTime(timezone=True))
    biography = Column(Text)
    photo_url = Column(String(500))
    imdb_id = Column(String(20))
    is_active = Column(Boolean, default=True, index=True)
    metadata = Column(JSONB, default={})
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    acted_in = relationship("Movie", secondary=movie_actor_association, back_populates="actors")
    directed = relationship("Movie", secondary=movie_director_association, back_populates="directors")
    wrote = relationship("Movie", secondary=movie_writer_association, back_populates="writers")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": str(self.id),
            "full_name": self.full_name,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "birth_place": self.birth_place,
            "death_date": self.death_date.isoformat() if self.death_date else None,
            "biography": self.biography,
            "photo_url": self.photo_url,
            "imdb_id": self.imdb_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class Review(Base):
    """
    Модель отзыва на фильм.
    
    Attributes:
        id: UUID отзыва
        movie_id: ID фильма
        user_id: ID пользователя (из User Service)
        rating: Оценка (1-5)
        title: Заголовок отзыва
        comment: Текст отзыва
        likes_count: Количество лайков
        is_verified: Проверенный отзыв
        is_active: Активен ли отзыв
        created_at: Дата создания
        updated_at: Дата обновления
    """
    
    __tablename__ = "reviews"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    movie_id = Column(UUID(as_uuid=True), ForeignKey('movies.id'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # Из User Service
    rating = Column(Integer, nullable=False)  # 1-5
    title = Column(String(255))
    comment = Column(Text)
    likes_count = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False)  # Проверенный покупкой/просмотром
    is_active = Column(Boolean, default=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    movie = relationship("Movie", back_populates="reviews")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": str(self.id),
            "movie_id": str(self.movie_id),
            "user_id": str(self.user_id),
            "rating": self.rating,
            "title": self.title,
            "comment": self.comment,
            "likes_count": self.likes_count,
            "is_verified": self.is_verified,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class Watchlist(Base):
    """
    Модель списка просмотра пользователя.
    
    Attributes:
        id: UUID записи
        user_id: ID пользователя (из User Service)
        movie_id: ID фильма
        added_at: Дата добавления
        notes: Заметки пользователя
    """
    
    __tablename__ = "watchlists"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)  # Из User Service
    movie_id = Column(UUID(as_uuid=True), ForeignKey('movies.id'), nullable=False, index=True)
    added_at = Column(DateTime(timezone=True), server_default=func.now())
    notes = Column(Text)
    
    # Relationships
    movie = relationship("Movie")
    
    def to_dict(self):
        """Преобразование в словарь."""
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "movie_id": str(self.movie_id),
            "added_at": self.added_at.isoformat(),
            "notes": self.notes,
            "movie": self.movie.to_dict() if self.movie else None
        }