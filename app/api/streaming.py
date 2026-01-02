from fastapi import APIRouter

from app.services.streaming_service import get_video_stream

router = APIRouter(prefix="/streaming", tags=["streaming"])


@router.get("/{movie_id}")
async def stream(movie_id: str, chunk: int = 0):
    data = await get_video_stream(movie_id, chunk)
    return {"movie_id": movie_id, "chunk": chunk, "data": data.decode()}
