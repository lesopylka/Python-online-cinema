#!/usr/bin/env python3
"""
Load test data into the system.
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sample data
SAMPLE_MOVIES = [
    {
        "id": str(uuid.uuid4()),
        "title": "Начало",
        "description": "Специалист по промышленному шпионажу, использующий технологию проникновения в сны.",
        "genres": ["фантастика", "боевик", "триллер"],
        "director": "Кристофер Нолан",
        "year": 2010,
        "rating": 8.8,
        "duration": 148,
        "country": "США",
        "language": "английский",
        "age_rating": "16+",
        "poster_url": "/posters/inception.jpg",
        "trailer_url": "/trailers/inception.mp4"
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Побег из Шоушенка",
        "description": "Бухгалтер Энди Дюфрейн обвинён в убийстве собственной жены.",
        "genres": ["драма"],
        "director": "Фрэнк Дарабонт",
        "year": 1994,
        "rating": 9.3,
        "duration": 142,
        "country": "США",
        "language": "английский",
        "age_rating": "16+",
        "poster_url": "/posters/shawshank.jpg"
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Темный рыцарь",
        "description": "Бэтмен поднимает ставки в войне с преступностью.",
        "genres": ["боевик", "триллер", "драма"],
        "director": "Кристофер Нолан",
        "year": 2008,
        "rating": 9.0,
        "duration": 152,
        "country": "США",
        "language": "английский",
        "age_rating": "16+",
        "poster_url": "/posters/dark_knight.jpg"
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Форрест Гамп",
        "description": "История жизни Форреста Гампа, человека с добрым сердцем.",
        "genres": ["драма", "мелодрама"],
        "director": "Роберт Земекис",
        "year": 1994,
        "rating": 8.8,
        "duration": 142,
        "country": "США",
        "language": "английский",
        "age_rating": "12+",
        "poster_url": "/posters/forrest_gump.jpg"
    },
    {
        "id": str(uuid.uuid4()),
        "title": "Интерстеллар",
        "description": "Фермер Купер отправляется в космическое путешествие.",
        "genres": ["фантастика", "драма", "приключения"],
        "director": "Кристофер Нолан",
        "year": 2014,
        "rating": 8.6,
        "duration": 169,
        "country": "США",
        "language": "английский",
        "age_rating": "12+",
        "poster_url": "/posters/interstellar.jpg"
    }
]

SAMPLE_ACTORS = [
    {
        "id": str(uuid.uuid4()),
        "name": "Леонардо ДиКаприо",
        "bio": "Американский актёр и продюсер.",
        "birth_date": "1974-11-11",
        "photo_url": "/actors/leonardo.jpg"
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Том Хэнкс",
        "bio": "Американский актёр, продюсер, режиссёр.",
        "birth_date": "1956-07-09",
        "photo_url": "/actors/tom_hanks.jpg"
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Мэттью Макконахи",
        "bio": "Американский актёр и продюсер.",
        "birth_date": "1969-11-04",
        "photo_url": "/actors/matthew.jpg"
    },
    {
        "id": str(uuid.uuid4()),
        "name": "Кристиан Бэйл",
        "bio": "Британский актёр.",
        "birth_date": "1974-01-30",
        "photo_url": "/actors/christian.jpg"
    }
]

SAMPLE_GENRES = [
    {"id": str(uuid.uuid4()), "name": "боевик", "description": "Фильмы с динамичными сценами и экшеном"},
    {"id": str(uuid.uuid4()), "name": "драма", "description": "Эмоциональные фильмы о человеческих отношениях"},
    {"id": str(uuid.uuid4()), "name": "комедия", "description": "Веселые и смешные фильмы"},
    {"id": str(uuid.uuid4()), "name": "фантастика", "description": "Фильмы о будущем и технологиях"},
    {"id": str(uuid.uuid4()), "name": "триллер", "description": "Напряженные фильмы с саспенсом"},
    {"id": str(uuid.uuid4()), "name": "мелодрама", "description": "Романтические фильмы о любви"},
    {"id": str(uuid.uuid4()), "name": "приключения", "description": "Фильмы о путешествиях и открытиях"}
]

async def create_test_users():
    """Create test users."""
    users = [
        {
            "id": str(uuid.uuid4()),
            "username": "test_user",
            "email": "user@example.com",
            "full_name": "Тестовый Пользователь",
            "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # "secret"
            "is_active": True,
            "subscription_type": "premium",
            "created_at": datetime.utcnow().isoformat()
        },
        {
            "id": str(uuid.uuid4()),
            "username": "admin",
            "email": "admin@example.com",
            "full_name": "Администратор Системы",
            "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",
            "is_active": True,
            "is_admin": True,
            "subscription_type": "premium",
            "created_at": datetime.utcnow().isoformat()
        }
    ]
    
    logger.info(f"Created {len(users)} test users")
    return users

async def create_watch_history(user_id: str, movie_ids: List[str]) -> List[Dict[str, Any]]:
    """Create sample watch history for a user."""
    history = []
    base_time = datetime.utcnow() - timedelta(days=30)
    
    for movie_id in movie_ids[:3]:  # User watched first 3 movies
        watch_time = base_time + timedelta(days=random.randint(0, 29))
        
        history.append({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "movie_id": movie_id,
            "watch_start": watch_time.isoformat(),
            "watch_duration": random.randint(30, 120),
            "completed": random.choice([True, False]),
            "device_type": random.choice(["web", "mobile", "tv"]),
            "created_at": watch_time.isoformat()
        })
    
    return history

async def generate_analytics_data(movie_ids: List[str], user_ids: List[str]) -> List[Dict[str, Any]]:
    """Generate sample analytics data."""
    analytics = []
    base_time = datetime.utcnow() - timedelta(days=30)
    
    # Generate views for each movie
    for movie_id in movie_ids:
        for day in range(30):
            date = base_time + timedelta(days=day)
            views_count = random.randint(50, 500)
            
            for _ in range(views_count):
                view_time = date + timedelta(
                    hours=random.randint(0, 23),
                    minutes=random.randint(0, 59)
                )
                
                analytics.append({
                    "id": str(uuid.uuid4()),
                    "event_type": "movie_view",
                    "movie_id": movie_id,
                    "user_id": random.choice(user_ids) if user_ids else None,
                    "timestamp": view_time.isoformat(),
                    "duration": random.randint(1, 120),
                    "device": random.choice(["web", "mobile", "smart_tv"]),
                    "location": random.choice(["Moscow", "Saint Petersburg", "Novosibirsk"]),
                    "completed": random.random() > 0.3
                })
    
    # Generate search events
    search_queries = ["боевик", "комедия", "фантастика", "новые фильмы", "смотреть онлайн"]
    for _ in range(1000):
        search_time = base_time + timedelta(
            days=random.randint(0, 29),
            hours=random.randint(0, 23)
        )
        
        analytics.append({
            "id": str(uuid.uuid4()),
            "event_type": "search",
            "user_id": random.choice(user_ids) if user_ids else None,
            "query": random.choice(search_queries),
            "results_count": random.randint(5, 50),
            "timestamp": search_time.isoformat(),
            "device": random.choice(["web", "mobile"])
        })
    
    return analytics

async def main():
    """Main function to load test data."""
    logger.info("Starting test data loading...")
    
    # Get movie IDs
    movie_ids = [movie["id"] for movie in SAMPLE_MOVIES]
    
    # Create test users
    users = await create_test_users()
    user_ids = [user["id"] for user in users]
    
    # Generate watch history
    watch_history = []
    for user in users:
        history = await create_watch_history(user["id"], movie_ids)
        watch_history.extend(history)
    
    # Generate analytics data
    analytics_data = await generate_analytics_data(movie_ids, user_ids)
    
    # Save data to JSON files
    data = {
        "movies": SAMPLE_MOVIES,
        "actors": SAMPLE_ACTORS,
        "genres": SAMPLE_GENRES,
        "users": users,
        "watch_history": watch_history,
        "analytics": analytics_data[:1000]  # Limit to 1000 records for demo
    }
    
    with open("test_data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Test data saved to test_data.json")
    logger.info(f"- Movies: {len(SAMPLE_MOVIES)}")
    logger.info(f"- Actors: {len(SAMPLE_ACTORS)}")
    logger.info(f"- Genres: {len(SAMPLE_GENRES)}")
    logger.info(f"- Users: {len(users)}")
    logger.info(f"- Watch history records: {len(watch_history)}")
    logger.info(f"- Analytics events: {len(analytics_data[:1000])}")
    
    # Print sample API calls
    print("\n" + "="*50)
    print("SAMPLE API CALLS FOR TESTING:")
    print("="*50)
    
    print("\n1. User registration:")
    print('curl -X POST http://localhost:8000/api/v1/users/register \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"username": "new_user", "email": "new@example.com", "password": "secret"}\'')
    
    print("\n2. User login:")
    print('curl -X POST http://localhost:8000/api/v1/users/login \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"username": "test_user", "password": "secret"}\'')
    
    print("\n3. Get movies list:")
    print('curl -X GET http://localhost:8000/api/v1/movies')
    
    print("\n4. Search movies:")
    print('curl -X GET "http://localhost:8000/api/v1/search?query=начало"')
    
    print("\n5. Start watching movie:")
    print('curl -X POST http://localhost:8000/api/v1/stream/start \\')
    print('  -H "Authorization: Bearer <YOUR_TOKEN>" \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"movie_id": "1"}\'')

if __name__ == "__main__":
    asyncio.run(main())