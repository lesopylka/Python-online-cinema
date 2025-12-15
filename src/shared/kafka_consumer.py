"""
Kafka consumer for handling event streams.
"""

import asyncio
import json
from typing import AsyncGenerator, List, Optional, Dict, Any
import logging
from aiokafka import AIOKafkaConsumer, ConsumerRecord

logger = logging.getLogger(__name__)

class KafkaConsumer:
    """Kafka consumer for consuming events."""
    
    def __init__(
        self,
        bootstrap_servers: List[str] = None,
        group_id: str = "default-group",
        topics: List[str] = None,
        auto_offset_reset: str = "latest",
        enable_auto_commit: bool = False,
        max_poll_records: int = 500
    ):
        self.bootstrap_servers = bootstrap_servers or ["localhost:9092"]
        self.group_id = group_id
        self.topics = topics or []
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        self.max_poll_records = max_poll_records
        
        self.consumer: Optional[AIOKafkaConsumer] = None
        
    async def connect(self):
        """Connect to Kafka broker."""
        try:
            self.consumer = AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                auto_offset_reset=self.auto_offset_reset,
                enable_auto_commit=self.enable_auto_commit,
                max_poll_records=self.max_poll_records
            )
            
            await self.consumer.start()
            logger.info(f"Kafka consumer connected to topics: {self.topics}")
            
        except Exception as e:
            logger.error(f"Failed to connect Kafka consumer: {str(e)}")
            raise
    
    async def consume(self) -> AsyncGenerator[ConsumerRecord, None]:
        """Consume messages from Kafka."""
        if not self.consumer:
            await self.connect()
            
        try:
            async for message in self.consumer:
                yield message
                
        except Exception as e:
            logger.error(f"Error consuming messages: {str(e)}")
            raise
    
    async def commit(self, message: ConsumerRecord):
        """Commit message offset."""
        if self.consumer:
            await self.consumer.commit()
    
    async def close(self):
        """Close the consumer."""
        if self.consumer:
            await self.consumer.stop()
            logger.info("Kafka consumer closed")
    
    async def subscribe(self, topics: List[str]):
        """Subscribe to new topics."""
        if self.consumer:
            self.consumer.subscribe(topics)
            self.topics.extend(topics)
            logger.info(f"Subscribed to new topics: {topics}")

# Global consumer instance
_consumer: Optional[KafkaConsumer] = None

def get_kafka_consumer(
    bootstrap_servers: List[str] = None,
    group_id: str = "default-group"
) -> KafkaConsumer:
    """Get Kafka consumer instance."""
    global _consumer
    
    if _consumer is None:
        _consumer = KafkaConsumer(
            bootstrap_servers=bootstrap_servers,
            group_id=group_id
        )
    
    return _consumer