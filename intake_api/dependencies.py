import json
import uuid
from redis.asyncio import Redis
from fastapi import HTTPException, status
from typing import Optional, Tuple

from common.config import settings


async def get_redis() -> Redis:
    """Зависимость для подключения к Redis"""
    return await Redis.from_url(settings.REDIS_URL)


async def verify_idempotency_key(
    redis: Redis,
    idempotency_key: uuid.UUID,
    current_request_data: Optional[dict] = None
) -> Tuple[bool, Optional[dict]]:
    """
    Checks the Idempotency-Key and returns:
    - (False, None): the key does not exist (new request)
    - (True, cached_data): the key exists (duplicate request)
    - Raise 409: the key exists but the data is different (conflict)
    """
    try:
        cached_data_str = await redis.get(f"idempotency:{idempotency_key}")
        if not cached_data_str:
            return False, None
        
        cached_data = json.loads(cached_data_str)
        
        if current_request_data is not None:
            cached_request_data = cached_data.get("request_data", {})
            if cached_request_data != current_request_data:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency-Key already used with different data"
                )
        
        return True, cached_data  # Key exists
            
    except HTTPException:
        raise
    except Exception as e:
        return False, None