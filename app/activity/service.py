# app/activity/service.py
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
import json
import structlog
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.config import get_settings
from app.database import get_db_session
from app.models import UserActivity, UserSession
from app.schemas.activity import ActivityEvent
from app.activity.storage import get_redis_client
from app.monitoring.metrics import (
    ACTIVE_SESSIONS,
    EVENTS_STORED,
    SESSIONS_UPDATED,
)

logger = structlog.get_logger()
settings = get_settings()


class ActivityService:
    def __init__(self):
        self.redis: Optional[Redis] = None
        self.db: Optional[AsyncSession] = None

    async def init(self):
        """Initialize connections"""
        self.redis = await get_redis_client()
        self.db = await anext(get_db_session())

    async def check_rate_limit(self, client_ip: str, event_count: int) -> bool:
        """Check rate limiting for client IP"""
        if not self.redis:
            await self.init()

        key = f"rate_limit:{client_ip}:{datetime.utcnow().strftime('%Y-%m-%d-%H')}"

        try:
            current = await self.redis.get(key)
            current_count = int(current) if current else 0

            if current_count + event_count > settings.RATE_LIMIT_PER_HOUR:
                logger.warning("Rate limit exceeded", client_ip=client_ip, current=current_count)
                return False

            # Increment counter
            await self.redis.incrby(key, event_count)
            # Set expiry to end of hour
            await self.redis.expire(key, 3600)

            return True

        except Exception as e:
            logger.error("Rate limit check failed", error=str(e))
            return True  # Fail open

    async def store_events(self, events: List[ActivityEvent]):
        """Store events in database"""
        if not self.db:
            await self.init()

        try:
            # Convert to database models
            db_events = []
            for event in events:
                db_event = UserActivity(
                    user_id=event.user_id,
                    session_id=event.session_id,
                    device_id=event.device_id,
                    ip_address=event.ip_address,
                    user_agent=event.user_agent,
                    event_type=event.event_type,
                    event_name=event.event_name,
                    page_url=event.page_url,
                    referrer_url=event.referrer_url,
                    content_id=event.content_id,
                    content_type=event.content_type,
                    metadata=event.metadata,
                    event_timestamp=event.timestamp,
                    duration=event.duration,
                    value=event.value,
                    created_at=datetime.utcnow(),
                    processed_at=datetime.utcnow()
                )
                db_events.append(db_event)

            # Bulk insert
            self.db.add_all(db_events)
            await self.db.commit()

            # Update metrics
            EVENTS_STORED.inc(len(db_events))

            # Update sessions
            await self._update_sessions(events)

            # Async export to ClickHouse
            asyncio.create_task(self._export_to_analytics(db_events))

            logger.info("Events stored", count=len(db_events))

        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to store events", error=str(e))
            raise

    async def _update_sessions(self, events: List[ActivityEvent]):
        """Update session information"""
        if not self.redis:
            await self.init()

        try:
            session_updates = {}

            for event in events:
                session_id = event.session_id

                if session_id not in session_updates:
                    session_updates[session_id] = {
                        'user_id': event.user_id,
                        'device_id': event.device_id,
                        'last_activity': event.timestamp,
                        'event_count': 0,
                        'video_plays': 0
                    }

                session_data = session_updates[session_id]
                session_data['event_count'] += 1

                if event.event_type == 'video_play':
                    session_data['video_plays'] += 1

            # Update Redis cache for real-time metrics
            for session_id, data in session_updates.items():
                # Update session in Redis
                session_key = f"session:{session_id}"
                await self.redis.hset(session_key, mapping={
                    'user_id': data['user_id'] or 'anonymous',
                    'last_activity': data['last_activity'].isoformat(),
                    'updated_at': datetime.utcnow().isoformat()
                })
                await self.redis.expire(session_key, 3600)  # 1 hour TTL

            # Update active sessions metric
            active_sessions = await self._count_active_sessions()
            ACTIVE_SESSIONS.set(active_sessions)

            SESSIONS_UPDATED.inc(len(session_updates))

        except Exception as e:
            logger.error("Failed to update sessions", error=str(e))

    async def _count_active_sessions(self) -> int:
        """Count active sessions (last 15 minutes)"""
        if not self.redis:
            await self.init()

        try:
            # Get all session keys
            keys = await self.redis.keys("session:*")
            active_count = 0

            for key in keys:
                session_data = await self.redis.hgetall(key)
                if session_data:
                    last_activity_str = session_data.get(b'last_activity', b'').decode()
                    if last_activity_str:
                        last_activity = datetime.fromisoformat(last_activity_str)
                        if datetime.utcnow() - last_activity < timedelta(minutes=15):
                            active_count += 1

            return active_count

        except Exception as e:
            logger.error("Failed to count active sessions", error=str(e))
            return 0

    async def get_session_events(self, session_id: str, limit: int = 100) -> List[Dict]:
        """Get events for a specific session"""
        if not self.db:
            await self.init()

        try:
            stmt = select(UserActivity).where(
                UserActivity.session_id == session_id
            ).order_by(
                UserActivity.event_timestamp.desc()
            ).limit(limit)

            result = await self.db.execute(stmt)
            events = result.scalars().all()

            return [
                {
                    'event_type': e.event_type,
                    'event_name': e.event_name,
                    'timestamp': e.event_timestamp.isoformat(),
                    'content_id': e.content_id,
                    'metadata': e.metadata
                }
                for e in events
            ]

        except Exception as e:
            logger.error("Failed to get session events", error=str(e), session_id=session_id)
            return []

    async def get_user_events(self, user_id: str, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get events for a specific user"""
        if not self.db:
            await self.init()

        try:
            stmt = select(UserActivity).where(
                UserActivity.user_id == user_id
            ).order_by(
                UserActivity.event_timestamp.desc()
            ).offset(offset).limit(limit)

            result = await self.db.execute(stmt)
            events = result.scalars().all()

            return [
                {
                    'event_type': e.event_type,
                    'event_name': e.event_name,
                    'timestamp': e.event_timestamp.isoformat(),
                    'content_id': e.content_id,
                    'session_id': e.session_id,
                    'metadata': e.metadata
                }
                for e in events
            ]

        except Exception as e:
            logger.error("Failed to get user events", error=str(e), user_id=user_id)
            return []

    async def update_session_activity(
            self,
            session_id: str,
            user_id: Optional[str] = None,
            client_ip: Optional[str] = None,
            user_agent: Optional[str] = None
    ):
        """Update session last activity"""
        if not self.redis:
            await self.init()

        try:
            session_key = f"session:{session_id}"

            updates = {
                'last_activity': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }

            if user_id:
                updates['user_id'] = user_id
            if client_ip:
                updates['client_ip'] = client_ip
            if user_agent:
                updates['user_agent'] = user_agent[:500]

            await self.redis.hset(session_key, mapping=updates)
            await self.redis.expire(session_key, 3600)  # 1 hour TTL

            logger.debug("Session activity updated", session_id=session_id)

        except Exception as e:
            logger.error("Failed to update session activity", error=str(e))

    async def _export_to_analytics(self, events: List[UserActivity]):
        """Export events to ClickHouse for analytics"""
        try:
            from clickhouse_driver import Client

            ch_client = Client(
                host=settings.CLICKHOUSE_HOST,
                port=settings.CLICKHOUSE_PORT,
                user=settings.CLICKHOUSE_USER,
                password=settings.CLICKHOUSE_PASSWORD,
                database=settings.CLICKHOUSE_DB
            )

            data = []
            for event in events:
                data.append([
                    str(event.id),
                    event.user_id or '',
                    event.session_id,
                    event.device_id or '',
                    event.ip_address or '',
                    event.user_agent or '',
                    event.event_type,
                    event.event_name,
                    event.page_url or '',
                    event.referrer_url or '',
                    event.content_id or '',
                    event.content_type or '',
                    json.dumps(event.metadata),
                    event.event_timestamp,
                    event.duration or 0.0,
                    event.value or 0.0,
                    event.created_at
                ])

            ch_client.execute(
                """
                INSERT INTO user_activity (id, user_id, session_id, device_id, ip_address, user_agent,
                                           event_type, event_name, page_url, referrer_url, content_id,
                                           content_type, metadata, event_timestamp, duration, value, created_at)
                VALUES
                """,
                data
            )

            logger.info("Events exported to ClickHouse", count=len(data))

        except ImportError:
            logger.warning("ClickHouse driver not installed")
        except Exception as e:
            logger.error("Failed to export to ClickHouse", error=str(e))