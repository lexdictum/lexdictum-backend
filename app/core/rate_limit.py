import time
from functools import lru_cache

import redis
from fastapi import status

from app.core.exceptions import LexDictumError


class RateLimitExceededError(LexDictumError):
    def __init__(
        self,
        message: str = (
            "Has superado el límite de mensajes por minuto. "
            "Inténtelo de nuevo en unos momentos."
        ),
        retry_after: int = 60,
    ):
        super().__init__(message, status_code=status.HTTP_429_TOO_MANY_REQUESTS)
        self.retry_after = retry_after


class ChatRateLimiter:
    def __init__(
        self,
        redis_url: str,
        limit: int,
        window_seconds: int = 60,
    ) -> None:
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self.limit = limit
        self.window = window_seconds

    def check(self, key: str) -> None:
        now = int(time.time())
        bucket = f"rate:chat:{key}:{now // self.window}"
        pipe = self._redis.pipeline()
        pipe.incr(bucket)
        pipe.expire(bucket, self.window + 1)
        count, _ = pipe.execute()
        if int(count) > self.limit:
            retry_after = self.window - (now % self.window)
            raise RateLimitExceededError(retry_after=retry_after)


@lru_cache
def get_chat_rate_limiter(redis_url: str, limit: int) -> ChatRateLimiter:
    return ChatRateLimiter(redis_url=redis_url, limit=limit)
