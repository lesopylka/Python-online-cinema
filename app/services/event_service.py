import json

from app.core.kafka import kafka_producer


async def send_event(event_type: str, event):
    payload = {
        "type": event_type,
        "data": event.dict(),
    }

    await kafka_producer.send_and_wait(
        topic="events",
        value=json.dumps(payload).encode(),
    )
