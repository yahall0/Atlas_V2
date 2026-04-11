import os
import redis as redis_lib

_client = None


def get_redis() -> redis_lib.Redis:
    """Return a lazy Redis client. Does not connect on import."""
    global _client
    if _client is None:
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
        _client = redis_lib.from_url(redis_url, decode_responses=True)
    return _client
