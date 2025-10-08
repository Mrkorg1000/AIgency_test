import json
import uuid
from redis.asyncio import Redis
from fastapi import HTTPException, status
from typing import Optional, Tuple

from common.config import settings


async def get_redis() -> Redis:
    """
    FastAPI dependency for Redis connection.
    
    Returns:
        Redis: Redis client with decoded responses.
    """
    return await Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def verify_idempotency_key(
    redis: Redis,
    idempotency_key: uuid.UUID,
    current_request_data: Optional[dict] = None
) -> Tuple[bool, Optional[dict]]:
    """
    Verifies idempotency key and checks for duplicate requests.
    
    Args:
        redis: Redis client instance
        idempotency_key: UUID idempotency key from request header
        current_request_data: Current request data to compare with cached
        
    Returns:
        Tuple[bool, Optional[dict]]: 
            - (False, None): Key does not exist (new request)
            - (True, cached_data): Key exists (duplicate request)
            
    Raises:
        HTTPException: 409 if key exists but data is different (conflict)
    """
    try:
        redis_key = f"idempotency:{idempotency_key}"
        cached_data_str = await redis.get(redis_key)
        
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
        
        return True, cached_data
            
    except HTTPException:
        raise
    except Exception as e:
        return False, None