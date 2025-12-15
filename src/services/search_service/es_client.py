"""
Клиент для работы с Elasticsearch.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import ElasticsearchException
from src.config.settings import settings

logger = logging.getLogger(__name__)


class ElasticsearchClient:
    """
    Клиент для работы с Elasticsearch.
    
    Attributes:
        es: AsyncElasticsearch client
        index_name: Название индекса для фильмов
        connected: Флаг подключения
    """
    
    def __init__(self):
        self.es = None
        self.index_name = "movies"
        self.connected = False
        self._connect()
    
    def _connect(self):
        """Подключение к Elasticsearch."""
        try:
            self.es = AsyncElasticsearch(
                [settings.ELASTICSEARCH_URL],
                verify_certs=False,
                request_timeout=30
            )
            self.connected = True
            logger.info(f"Connected to Elasticsearch at {settings.ELASTICSEARCH_URL}")
            
        except Exception as e:
            logger.error(f"Failed to connect to Elasticsearch: {e}")
            self.connected = False
    
    async def create_index(self):
        """
        Создание индекса с маппингом и настройками.
        """
        if not self.connected or not self.es:
            logger.error("Elasticsearch not connected")
            return False
        
        try:
            # Проверяем существует ли индекс
            if await self.es.indices.exists(index=self.index_name):
                logger.info(f"Index {self.index_name} already exists")
                return True
            
            # Создаем индекс с маппингом
            index_body = {
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 1,
                    "analysis": {
                        "analyzer": {
                            "russian": {
                                "type": "custom",
                                "tokenizer": "standard",
                                "filter": [
                                    "lowercase",
                                    "russian_stop",
                                    "russian_stemmer"
                                ]
                            },
                            "english": {
                                "type": "custom",
                                "tokenizer": "standard",
                                "filter": [
                                    "lowercase",
                                    "english_stop",
                                    "english_stemmer"
                                ]
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
                            },
                            "english_stop": {
                                "type": "stop",
                                "stopwords": "_english_"
                            },
                            "english_stemmer": {
                                "type": "stemmer",
                                "language": "english"
                            }
                        }
                    }
                },
                "mappings": {
                    "properties": {
                        "id": {"type": "keyword"},
                        "title": {
                            "type": "text",
                            "analyzer": "russian",
                            "fields": {
                                "keyword": {"type": "keyword", "ignore_above": 256}
                            }
                        },
                        "original_title": {
                            "type": "text",
                            "analyzer": "english",
                            "fields": {
                                "keyword": {"type": "keyword", "ignore_above": 256}
                            }
                        },
                        "description": {
                            "type": "text",
                            "analyzer": "russian"
                        },
                        "content_type": {"type": "keyword"},
                        "release_year": {"type": "integer"},
                        "duration_minutes": {"type": "integer"},
                        "rating": {"type": "float"},
                        "age_rating": {"type": "keyword"},
                        "poster_url": {"type": "keyword", "index": False},
                        "backdrop_url": {"type": "keyword", "index": False},
                        "trailer_url": {"type": "keyword", "index": False},
                        "country": {"type": "keyword"},
                        "language": {"type": "keyword"},
                        "subtitles": {"type": "keyword"},
                        "is_active": {"type": "boolean"},
                        "genres": {
                            "type": "nested",
                            "properties": {
                                "id": {"type": "integer"},
                                "name": {"type": "keyword"},
                                "slug": {"type": "keyword"}
                            }
                        },
                        "actors": {
                            "type": "nested",
                            "properties": {
                                "id": {"type": "keyword"},
                                "full_name": {
                                    "type": "text",
                                    "analyzer": "russian",
                                    "fields": {
                                        "keyword": {"type": "keyword"}
                                    }
                                }
                            }
                        },
                        "directors": {
                            "type": "nested",
                            "properties": {
                                "id": {"type": "keyword"},
                                "full_name": {
                                    "type": "text",
                                    "analyzer": "russian",
                                    "fields": {
                                        "keyword": {"type": "keyword"}
                                    }
                                }
                            }
                        },
                        "created_at": {"type": "date"},
                        "updated_at": {"type": "date"},
                        "search_suggest": {
                            "type": "completion",
                            "contexts": [
                                {
                                    "name": "content_type",
                                    "type": "category"
                                }
                            ]
                        }
                    }
                }
            }
            
            await self.es.indices.create(
                index=self.index_name,
                body=index_body
            )
            
            logger.info(f"Index {self.index_name} created successfully")
            return True
            
        except ElasticsearchException as e:
            logger.error(f"Failed to create index: {e}")
            return False
    
    async def index_movie(self, movie_data: Dict[str, Any]) -> bool:
        """
        Индексация фильма в Elasticsearch.
        
        Args:
            movie_data: Данные фильма
            
        Returns:
            True если успешно, False если ошибка
        """
        if not self.connected or not self.es:
            logger.error("Elasticsearch not connected")
            return False
        
        try:
            # Подготавливаем данные для индексации
            doc = {
                "id": movie_data.get("id"),
                "title": movie_data.get("title"),
                "original_title": movie_data.get("original_title"),
                "description": movie_data.get("description"),
                "content_type": movie_data.get("content_type"),
                "release_year": movie_data.get("release_year"),
                "duration_minutes": movie_data.get("duration_minutes"),
                "rating": movie_data.get("rating"),
                "age_rating": movie_data.get("age_rating"),
                "poster_url": movie_data.get("poster_url"),
                "backdrop_url": movie_data.get("backdrop_url"),
                "trailer_url": movie_data.get("trailer_url"),
                "country": movie_data.get("country"),
                "language": movie_data.get("language"),
                "subtitles": movie_data.get("subtitles", []),
                "is_active": movie_data.get("is_active", True),
                "genres": movie_data.get("genres", []),
                "actors": movie_data.get("actors", []),
                "directors": movie_data.get("directors", []),
                "created_at": movie_data.get("created_at"),
                "updated_at": movie_data.get("updated_at"),
                "search_suggest": {
                    "input": [
                        movie_data.get("title"),
                        movie_data.get("original_title")
                    ],
                    "contexts": {
                        "content_type": [movie_data.get("content_type")]
                    }
                }
            }
            
            # Удаляем None значения
            doc = {k: v for k, v in doc.items() if v is not None}
            
            await self.es.index(
                index=self.index_name,
                id=movie_data.get("id"),
                document=doc
            )
            
            logger.debug(f"Movie indexed: {movie_data.get('id')}")
            return True
            
        except ElasticsearchException as e:
            logger.error(f"Failed to index movie {movie_data.get('id')}: {e}")
            return False
    
    async def update_movie(self, movie_id: str, update_data: Dict[str, Any]) -> bool:
        """
        Обновление фильма в индексе.
        
        Args:
            movie_id: ID фильма
            update_data: Данные для обновления
            
        Returns:
            True если успешно, False если ошибка
        """
        if not self.connected or not self.es:
            logger.error("Elasticsearch not connected")
            return False
        
        try:
            await self.es.update(
                index=self.index_name,
                id=movie_id,
                body={"doc": update_data}
            )
            
            logger.debug(f"Movie updated in index: {movie_id}")
            return True
            
        except ElasticsearchException as e:
            logger.error(f"Failed to update movie {movie_id}: {e}")
            return False
    
    async def delete_movie(self, movie_id: str) -> bool:
        """
        Удаление фильма из индекса.
        
        Args:
            movie_id: ID фильма
            
        Returns:
            True если успешно, False если ошибка
        """
        if not self.connected or not self.es:
            logger.error("Elasticsearch not connected")
            return False
        
        try:
            await self.es.delete(
                index=self.index_name,
                id=movie_id
            )
            
            logger.debug(f"Movie deleted from index: {movie_id}")
            return True
            
        except ElasticsearchException as e:
            logger.error(f"Failed to delete movie {movie_id}: {e}")
            return False
    
    async def search_movies(
        self,
        query: str = "",
        filters: Optional[Dict[str, Any]] = None,
        sort_by: Optional[str] = None,
        sort_order: str = "desc",
        page: int = 1,
        size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Поиск фильмов по тексту с фильтрами.
        
        Args:
            query: Поисковый запрос
            filters: Фильтры поиска
            sort_by: Поле сортировки
            sort_order: Порядок сортировки
            page: Номер страницы
            size: Размер страницы
            
        Returns:
            Кортеж (результаты поиска, общее количество)
        """
        if not self.connected or not self.es:
            logger.error("Elasticsearch not connected")
            return [], 0
        
        try:
            # Базовый запрос
            search_body = {
                "query": {
                    "bool": {
                        "must": [],
                        "filter": []
                    }
                },
                "from": (page - 1) * size,
                "size": size
            }
            
            # Текстовый поиск
            if query and query.strip():
                search_body["query"]["bool"]["must"].append({
                    "multi_match": {
                        "query": query,
                        "fields": [
                            "title^3",  # Больший вес у названия
                            "original_title^2",
                            "description",
                            "actors.full_name",
                            "directors.full_name"
                        ],
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                        "operator": "or"
                    }
                })
            else:
                # Если нет текстового запроса, ищем все документы
                search_body["query"]["bool"]["must"].append({"match_all": {}})
            
            # Применяем фильтры
            if filters:
                # Фильтр по жанрам
                if "genre_ids" in filters and filters["genre_ids"]:
                    genre_ids = [str(gid) for gid in filters["genre_ids"]]
                    search_body["query"]["bool"]["filter"].append({
                        "nested": {
                            "path": "genres",
                            "query": {
                                "terms": {"genres.id": genre_ids}
                            }
                        }
                    })
                
                # Фильтр по типу контента
                if "content_type" in filters:
                    search_body["query"]["bool"]["filter"].append({
                        "term": {"content_type": filters["content_type"]}
                    })
                
                # Фильтр по рейтингу
                if "min_rating" in filters:
                    search_body["query"]["bool"]["filter"].append({
                        "range": {"rating": {"gte": filters["min_rating"]}}
                    })
                if "max_rating" in filters:
                    search_body["query"]["bool"]["filter"].append({
                        "range": {"rating": {"lte": filters["max_rating"]}}
                    })
                
                # Фильтр по году
                if "year_from" in filters:
                    search_body["query"]["bool"]["filter"].append({
                        "range": {"release_year": {"gte": filters["year_from"]}}
                    })
                if "year_to" in filters:
                    search_body["query"]["bool"]["filter"].append({
                        "range": {"release_year": {"lte": filters["year_to"]}}
                    })
                
                # Фильтр по стране
                if "country" in filters:
                    search_body["query"]["bool"]["filter"].append({
                        "term": {"country": filters["country"]}
                    })
                
                # Фильтр по языку
                if "language" in filters:
                    search_body["query"]["bool"]["filter"].append({
                        "term": {"language": filters["language"]}
                    })
                
                # Фильтр по возрастному рейтингу
                if "age_rating" in filters:
                    search_body["query"]["bool"]["filter"].append({
                        "term": {"age_rating": filters["age_rating"]}
                    })
                
                # Только активные фильмы
                if "is_active" in filters:
                    search_body["query"]["bool"]["filter"].append({
                        "term": {"is_active": filters["is_active"]}
                    })
                else:
                    # По умолчанию только активные
                    search_body["query"]["bool"]["filter"].append({
                        "term": {"is_active": True}
                    })
            
            # Настройка сортировки
            if sort_by:
                sort_field = sort_by
                if sort_by == "title":
                    sort_field = "title.keyword"
                elif sort_by == "rating":
                    sort_field = "rating"
                elif sort_by == "release_year":
                    sort_field = "release_year"
                elif sort_by == "created_at":
                    sort_field = "created_at"
                
                search_body["sort"] = [
                    {sort_field: {"order": sort_order}}
                ]
            else:
                # Сортировка по релевантности если есть запрос, иначе по дате создания
                if query and query.strip():
                    search_body["sort"] = ["_score"]
                else:
                    search_body["sort"] = [{"created_at": {"order": "desc"}}]
            
            # Выполняем поиск
            response = await self.es.search(
                index=self.index_name,
                body=search_body
            )
            
            # Извлекаем результаты
            hits = response.get("hits", {}).get("hits", [])
            total = response.get("hits", {}).get("total", {}).get("value", 0)
            
            results = []
            for hit in hits:
                source = hit["_source"]
                source["_score"] = hit.get("_score", 0)
                source["_id"] = hit["_id"]
                results.append(source)
            
            logger.debug(f"Search completed: query='{query}', found={total}")
            return results, total
            
        except ElasticsearchException as e:
            logger.error(f"Search failed: {e}")
            return [], 0
    
    async def autocomplete(
        self,
        query: str,
        size: int = 10,
        content_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Автодополнение поисковых запросов.
        
        Args:
            query: Часть запроса
            size: Количество результатов
            content_type: Ограничение по типу контента
            
        Returns:
            Список предложений
        """
        if not self.connected or not self.es:
            logger.error("Elasticsearch not connected")
            return []
        
        try:
            suggest_body = {
                "size": 0,
                "suggest": {
                    "movie_suggest": {
                        "prefix": query,
                        "completion": {
                            "field": "search_suggest",
                            "size": size,
                            "fuzzy": {
                                "fuzziness": 1
                            }
                        }
                    }
                }
            }
            
            # Добавляем контекст если указан тип контента
            if content_type:
                suggest_body["suggest"]["movie_suggest"]["completion"]["contexts"] = {
                    "content_type": [content_type]
                }
            
            response = await self.es.search(
                index=self.index_name,
                body=suggest_body
            )
            
            suggestions = []
            for option in response["suggest"]["movie_suggest"][0]["options"]:
                suggestions.append({
                    "text": option["text"],
                    "score": option.get("_score", 0),
                    "source": option.get("_source", {})
                })
            
            return suggestions
            
        except ElasticsearchException as e:
            logger.error(f"Autocomplete failed: {e}")
            return []
    
    async def search_similar(
        self,
        movie_id: str,
        size: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Поиск похожих фильмов.
        
        Args:
            movie_id: ID фильма для поиска похожих
            size: Количество результатов
            
        Returns:
            Список похожих фильмов
        """
        if not self.connected or not self.es:
            logger.error("Elasticsearch not connected")
            return []
        
        try:
            # Получаем фильм
            movie = await self.es.get(index=self.index_name, id=movie_id)
            if not movie or not movie.get("found"):
                return []
            
            source = movie["_source"]
            genres = source.get("genres", [])
            actors = source.get("actors", [])
            
            # Поиск по похожим жанрам и актерам
            search_body = {
                "query": {
                    "bool": {
                        "must_not": {
                            "term": {"_id": movie_id}
                        },
                        "should": [
                            # По жанрам
                            {
                                "nested": {
                                    "path": "genres",
                                    "query": {
                                        "terms": {
                                            "genres.id": [g["id"] for g in genres[:3]]
                                        }
                                    },
                                    "boost": 2.0
                                }
                            },
                            # По актерам
                            {
                                "nested": {
                                    "path": "actors",
                                    "query": {
                                        "terms": {
                                            "actors.id": [a["id"] for a in actors[:5]]
                                        }
                                    },
                                    "boost": 1.5
                                }
                            },
                            # По режиссерам
                            {
                                "nested": {
                                    "path": "directors",
                                    "query": {
                                        "terms": {
                                            "directors.id": [d["id"] for d in source.get("directors", [])[:3]]
                                        }
                                    },
                                    "boost": 1.2
                                }
                            }
                        ],
                        "minimum_should_match": 1,
                        "filter": [
                            {"term": {"is_active": True}}
                        ]
                    }
                },
                "size": size
            }
            
            response = await self.es.search(
                index=self.index_name,
                body=search_body
            )
            
            results = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                source["_score"] = hit.get("_score", 0)
                source["_id"] = hit["_id"]
                results.append(source)
            
            return results
            
        except ElasticsearchException as e:
            logger.error(f"Similar search failed for movie {movie_id}: {e}")
            return []
    
    async def get_index_stats(self) -> Dict[str, Any]:
        """
        Получение статистики индекса.
        
        Returns:
            Статистика индекса
        """
        if not self.connected or not self.es:
            logger.error("Elasticsearch not connected")
            return {}
        
        try:
            stats = await self.es.indices.stats(index=self.index_name)
            return {
                "total_documents": stats["_all"]["total"]["docs"]["count"],
                "total_size": stats["_all"]["total"]["store"]["size_in_bytes"],
                "index_name": self.index_name
            }
            
        except ElasticsearchException as e:
            logger.error(f"Failed to get index stats: {e}")
            return {}
    
    async def health_check(self) -> bool:
        """
        Проверка здоровья Elasticsearch.
        
        Returns:
            True если Elasticsearch доступен
        """
        if not self.es:
            return False
        
        try:
            health = await self.es.cluster.health()
            return health.get("status") in ["green", "yellow"]
            
        except ElasticsearchException as e:
            logger.error(f"Elasticsearch health check failed: {e}")
            return False
    
    async def close(self):
        """Закрытие соединения с Elasticsearch."""
        if self.es:
            await self.es.close()
            self.connected = False
            logger.info("Elasticsearch connection closed")


# Глобальный инстанс клиента
es_client = ElasticsearchClient()