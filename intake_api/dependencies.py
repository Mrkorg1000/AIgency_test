import json
import uuid
from redis.asyncio import Redis
from fastapi import HTTPException, status
from typing import Optional, Tuple

from common.config import settings


async def get_redis() -> Redis:
    """Зависимость для подключения к Redis"""
    return await Redis.from_url(settings.REDIS_URL, decode_responses=True)


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
        redis_key = f"idempotency:{idempotency_key}"
        print(f"[verify_idempotency_key] Checking key={redis_key}")
        
        cached_data_str = await redis.get(redis_key)
        print(f"[verify_idempotency_key] cached_data_str={cached_data_str is not None}")
        
        if not cached_data_str:
            print(f"[verify_idempotency_key] Key not found, returning False")
            return False, None
        
        cached_data = json.loads(cached_data_str)
        print(f"[verify_idempotency_key] Cached data loaded successfully")
        
        if current_request_data is not None:
            cached_request_data = cached_data.get("request_data", {})
            if cached_request_data != current_request_data:
                print(f"[verify_idempotency_key] Data mismatch! Raising 409")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency-Key already used with different data"
                )
        
        print(f"[verify_idempotency_key] Key exists with matching data, returning True")
        return True, cached_data  # Key exists
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[verify_idempotency_key] Exception: {e}")
        return False, None