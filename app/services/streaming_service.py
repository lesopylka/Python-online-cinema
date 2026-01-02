from app.core.storage import get_chunk_from_storage


async def get_video_stream(movie_id: str, chunk: int):
    return get_chunk_from_storage(movie_id, chunk)
