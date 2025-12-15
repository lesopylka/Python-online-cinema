"""
ETL Pipeline for data synchronization between services.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any
import time

from src.shared.logging import setup_logging
from src.shared.kafka_producer import KafkaProducer
from src.shared.kafka_consumer import KafkaConsumer
from .extractors import DataExtractor
from .transformers import DataTransformer
from .loaders import DataLoader

logger = setup_logging(__name__)

class ETLPipeline:
    """Main ETL pipeline class."""
    
    def __init__(self):
        self.extractor = DataExtractor()
        self.transformer = DataTransformer()
        self.loader = DataLoader()
        self.kafka_producer = KafkaProducer()
        self.kafka_consumer = KafkaConsumer(
            group_id="etl-pipeline",
            topics=["catalog_updates", "search_reindex"]
        )
        
    async def run_full_sync(self):
        """Run full synchronization of all data."""
        logger.info("Starting full ETL sync")
        
        try:
            # Extract data from source
            logger.info("Extracting data...")
            movies_data = await self.extractor.extract_movies()
            actors_data = await self.extractor.extract_actors()
            genres_data = await self.extractor.extract_genres()
            
            # Transform data
            logger.info("Transforming data...")
            transformed_movies = await self.transformer.transform_movies(movies_data)
            transformed_actors = await self.transformer.transform_actors(actors_data)
            transformed_genres = await self.transformer.transform_genres(genres_data)
            
            # Load data to destinations
            logger.info("Loading data to search index...")
            await self.loader.load_to_elasticsearch(
                movies=transformed_movies,
                actors=transformed_actors,
                genres=transformed_genres
            )
            
            logger.info("Loading data to analytics...")
            await self.loader.load_to_analytics(
                movies=transformed_movies,
                actors=transformed_actors
            )
            
            # Send completion event
            await self.kafka_producer.send_event("etl_complete", {
                "timestamp": datetime.utcnow().isoformat(),
                "movies_count": len(transformed_movies),
                "actors_count": len(transformed_actors),
                "status": "success"
            })
            
            logger.info(f"Full ETL sync completed: {len(transformed_movies)} movies, {len(transformed_actors)} actors")
            
        except Exception as e:
            logger.error(f"ETL pipeline failed: {str(e)}")
            
            # Send error event
            await self.kafka_producer.send_event("etl_error", {
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "status": "failed"
            })
            raise
    
    async def run_incremental_sync(self):
        """Run incremental sync based on Kafka events."""
        logger.info("Starting incremental ETL sync")
        
        async for message in self.kafka_consumer.consume():
            try:
                event_data = json.loads(message.value.decode('utf-8'))
                event_type = message.key.decode('utf-8') if message.key else "unknown"
                
                await self.process_event(event_type, event_data)
                
                await self.kafka_consumer.commit(message)
                
            except Exception as e:
                logger.error(f"Error processing event: {str(e)}")
    
    async def process_event(self, event_type: str, event_data: Dict[str, Any]):
        """Process ETL event."""
        if event_type == "movie_updated":
            await self.process_movie_update(event_data)
        elif event_type == "movie_deleted":
            await self.process_movie_delete(event_data)
        elif event_type == "search_reindex":
            await self.run_full_sync()
        else:
            logger.warning(f"Unknown event type: {event_type}")
    
    async def process_movie_update(self, movie_data: Dict[str, Any]):
        """Process movie update event."""
        logger.info(f"Processing movie update: {movie_data.get('id')}")
        
        try:
            # Transform movie data
            transformed_movie = await self.transformer.transform_movie(movie_data)
            
            # Update search index
            await self.loader.update_elasticsearch_movie(transformed_movie)
            
            # Update analytics
            await self.loader.update_analytics_movie(transformed_movie)
            
            logger.info(f"Movie {movie_data.get('id')} updated successfully")
            
        except Exception as e:
            logger.error(f"Failed to update movie {movie_data.get('id')}: {str(e)}")
    
    async def process_movie_delete(self, movie_data: Dict[str, Any]):
        """Process movie delete event."""
        movie_id = movie_data.get('id')
        logger.info(f"Processing movie delete: {movie_id}")
        
        try:
            # Remove from search index
            await self.loader.delete_elasticsearch_movie(movie_id)
            
            # Update analytics (mark as deleted)
            await self.loader.delete_analytics_movie(movie_id)
            
            logger.info(f"Movie {movie_id} deleted successfully")
            
        except Exception as e:
            logger.error(f"Failed to delete movie {movie_id}: {str(e)}")
    
    async def sync_user_activity(self, start_date: datetime, end_date: datetime):
        """Sync user activity data to analytics."""
        logger.info(f"Syncing user activity from {start_date} to {end_date}")
        
        try:
            # Extract user activity
            activities = await self.extractor.extract_user_activity(start_date, end_date)
            
            # Transform activities
            transformed_activities = await self.transformer.transform_user_activities(activities)
            
            # Load to analytics
            await self.loader.load_user_activities(transformed_activities)
            
            logger.info(f"User activity sync completed: {len(transformed_activities)} activities")
            
        except Exception as e:
            logger.error(f"User activity sync failed: {str(e)}")
            raise

async def main():
    """Main ETL pipeline entry point."""
    pipeline = ETLPipeline()
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="ETL Pipeline for Online Cinema")
    parser.add_argument("--mode", choices=["full", "incremental", "activity"], default="incremental")
    parser.add_argument("--start-date", help="Start date for activity sync (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="End date for activity sync (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    if args.mode == "full":
        await pipeline.run_full_sync()
    elif args.mode == "incremental":
        await pipeline.run_incremental_sync()
    elif args.mode == "activity":
        start_date = datetime.fromisoformat(args.start_date) if args.start_date else datetime.utcnow() - timedelta(days=1)
        end_date = datetime.fromisoformat(args.end_date) if args.end_date else datetime.utcnow()
        await pipeline.sync_user_activity(start_date, end_date)

if __name__ == "__main__":
    asyncio.run(main())