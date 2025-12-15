#!/usr/bin/env python3
"""
Create Elasticsearch indexes for search service.
"""

import asyncio
import json
import logging
from typing import Dict, Any
from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ELASTICSEARCH_URL = "http://localhost:9200"

# Movie index mapping
MOVIE_INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 2,
        "number_of_replicas": 1,
        "analysis": {
            "analyzer": {
                "russian_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "russian_stop", "russian_stemmer"]
                }
            },
            "filter": {
                "russian_stop": {
                    "type": "stop",
                    "stopwords": "_russian_"
                },
                "russian_stemmer": {
                    "type": "stemmer",
                    "language": "russian"
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "title": {
                "type": "text",
                "analyzer": "russian_analyzer",
                "fields": {
                    "keyword": {"type": "keyword"}
                }
            },
            "description": {
                "type": "text",
                "analyzer": "russian_analyzer"
            },
            "genres": {
                "type": "keyword"
            },
            "actors": {
                "type": "nested",
                "properties": {
                    "id": {"type": "keyword"},
                    "name": {"type": "text"},
                    "role": {"type": "keyword"}
                }
            },
            "director": {"type": "keyword"},
            "year": {"type": "integer"},
            "rating": {"type": "float"},
            "duration": {"type": "integer"},  # in minutes
            "country": {"type": "keyword"},
            "language": {"type": "keyword"},
            "subtitles": {"type": "keyword"},
            "age_rating": {"type": "keyword"},
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"},
            "popularity_score": {"type": "float"},
            "is_active": {"type": "boolean"},
            "poster_url": {"type": "keyword"},
            "trailer_url": {"type": "keyword"},
            "video_url": {"type": "keyword"}
        }
    }
}

# Actor index mapping
ACTOR_INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 1
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "name": {
                "type": "text",
                "fields": {
                    "keyword": {"type": "keyword"}
                }
            },
            "bio": {"type": "text"},
            "birth_date": {"type": "date"},
            "movies": {
                "type": "nested",
                "properties": {
                    "id": {"type": "keyword"},
                    "title": {"type": "text"},
                    "role": {"type": "keyword"},
                    "year": {"type": "integer"}
                }
            },
            "photo_url": {"type": "keyword"},
            "created_at": {"type": "date"}
        }
    }
}

async def create_index(es: AsyncElasticsearch, index_name: str, mapping: Dict[str, Any]) -> bool:
    """Create Elasticsearch index with mapping."""
    try:
        # Check if index exists
        if await es.indices.exists(index=index_name):
            logger.info(f"Index '{index_name}' already exists, skipping...")
            return True
        
        # Create index
        await es.indices.create(index=index_name, body=mapping)
        logger.info(f"Index '{index_name}' created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create index '{index_name}': {str(e)}")
        return False

async def create_all_indexes():
    """Create all required Elasticsearch indexes."""
    es = AsyncElasticsearch([ELASTICSEARCH_URL])
    
    try:
        # Check Elasticsearch connection
        if not await es.ping():
            logger.error("Cannot connect to Elasticsearch")
            return False
        
        logger.info("Connected to Elasticsearch")
        
        # Create indexes
        indexes = [
            ("movies", MOVIE_INDEX_MAPPING),
            ("actors", ACTOR_INDEX_MAPPING)
        ]
        
        success = True
        for index_name, mapping in indexes:
            if not await create_index(es, index_name, mapping):
                success = False
        
        return success
        
    except Exception as e:
        logger.error(f"Error creating indexes: {str(e)}")
        return False
        
    finally:
        await es.close()

async def load_sample_data():
    """Load sample data into Elasticsearch."""
    es = AsyncElasticsearch([ELASTICSEARCH_URL])
    
    try:
        # Sample movies data
        movies = [
            {
                "_index": "movies",
                "_id": "1",
                "_source": {
                    "id": "1",
                    "title": "Начало",
                    "description": "Специалист по промышленному шпионажу, использующий технологию проникновения в сны, получает задание внедрить идею в сознание наследника промышленной империи.",
                    "genres": ["фантастика", "боевик", "триллер"],
                    "director": "Кристофер Нолан",
                    "year": 2010,
                    "rating": 8.8,
                    "duration": 148,
                    "country": "США",
                    "language": "английский",
                    "age_rating": "16+",
                    "popularity_score": 9.5,
                    "is_active": True,
                    "poster_url": "/posters/inception.jpg",
                    "trailer_url": "/trailers/inception.mp4"
                }
            },
            {
                "_index": "movies",
                "_id": "2",
                "_source": {
                    "id": "2",
                    "title": "Побег из Шоушенка",
                    "description": "Бухгалтер Энди Дюфрейн обвинён в убийстве собственной жены и её любовника. Оказавшись в тюрьме под названием Шоушенк, он сталкивается с жестокостью и беззаконием, царящими по обе стороны решётки.",
                    "genres": ["драма"],
                    "director": "Фрэнк Дарабонт",
                    "year": 1994,
                    "rating": 9.3,
                    "duration": 142,
                    "country": "США",
                    "language": "английский",
                    "age_rating": "16+",
                    "popularity_score": 9.8,
                    "is_active": True,
                    "poster_url": "/posters/shawshank.jpg"
                }
            }
        ]
        
        # Load sample data
        success, failed = await async_bulk(es, movies)
        logger.info(f"Loaded {success} documents, failed: {len(failed)}")
        
        # Refresh indices
        await es.indices.refresh(index="movies")
        
        return True
        
    except Exception as e:
        logger.error(f"Error loading sample data: {str(e)}")
        return False
        
    finally:
        await es.close()

async def main():
    """Main function."""
    logger.info("Starting Elasticsearch index creation...")
    
    # Create indexes
    if not await create_all_indexes():
        logger.error("Failed to create indexes")
        return
    
    # Ask if we should load sample data
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--load-data":
        logger.info("Loading sample data...")
        await load_sample_data()
    
    logger.info("Index creation completed successfully")

if __name__ == "__main__":
    asyncio.run(main())