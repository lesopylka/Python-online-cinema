CHUNK_SIZE = 1024 * 1024  # 1 MB


def get_chunk_from_storage(movie_id: str, chunk: int) -> bytes:
    """
    Заглушка для хранилища видео
    """
    return f"Video chunk {chunk} for movie {movie_id}".encode()
