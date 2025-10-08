from datetime import datetime
import hashlib
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Header, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from common.database import get_async_session
from dependencies import get_redis, verify_idempotency_key
from common.models import Lead
from common.schemas import LeadCreate, LeadResponse


leads_router = APIRouter(
    prefix="/leads",
    tags=["leads"],
)


@leads_router.post(
    "/",
    response_model=LeadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"model": LeadResponse, "description": "Idempotent response"},
        409: {"description": "Idempotency-Key conflict"},
        400: {"description": "Idempotency-Key header required"}
    }
)
async def create_lead(
    lead_data: LeadCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    redis: Redis = Depends(get_redis),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Creates a new lead with idempotency support.
    
    Args:
        lead_data: Lead data to create
        idempotency_key: UUID idempotency key from header (required)
        redis: Redis client (injected)
        db: Database session (injected)
        
    Returns:
        LeadResponse: Created lead data (201) or cached response (200)
        
    Raises:
        HTTPException: 422 if idempotency key is not a valid UUID
        HTTPException: 409 if idempotency key used with different data
        HTTPException: 500 on internal errors
    """
    try:
        # Validate UUID format at endpoint level (return 422 with clear message)
        try:
            validated_idempotency_key = uuid.UUID(idempotency_key)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Idempotency-Key must be a valid UUID",
            )
        
        # Check idempotency
        is_duplicate, cached_data = await verify_idempotency_key(
            redis, 
            validated_idempotency_key,
            lead_data.dict()
        )
        
        if is_duplicate:
            # Return cached response with 200 to indicate idempotent request
            return JSONResponse(
                content=cached_data["response_data"],
                status_code=status.HTTP_200_OK
            )
        
        # Create lead in database
        lead = Lead(**lead_data.dict())
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
        
        # Prepare cache payload
        cache_payload = {
            "status_code": status.HTTP_201_CREATED,
            "response_data": LeadResponse.model_validate(lead).model_dump(mode="json"),
            "request_data": lead_data.dict()  # Store for future verification
        }
        
        # Save to Redis cache (24 hours TTL)
        await redis.setex(
            f"idempotency:{validated_idempotency_key}",
            86400,
            json.dumps(cache_payload)
        )
        
        # Publish event to Redis Stream for triage worker
        from common.config import settings
        await redis.xadd(settings.REDIS_STREAM, {
            "event_id": str(uuid.uuid4()),
            "type": "lead.created",
            "lead_id": str(lead.id),
            "note": lead.note,
            "content_hash": hashlib.sha256(lead.note.encode()).hexdigest(),
            "occurred_at": datetime.utcnow().isoformat()
        })
        
        return LeadResponse.from_orm(lead)
        
    except HTTPException as e:
        raise e
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating lead: {str(e)}"
        )
        
        
@leads_router.get(
    "/{lead_id}",
    response_model=LeadResponse,
    responses={
        200: {"description": "Lead found"},
        404: {"description": "Lead not found"}
    }
)
async def get_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Retrieves a lead by UUID.
    
    Args:
        lead_id: UUID of the lead to retrieve
        db: Database session (injected)
        
    Returns:
        LeadResponse: Lead data
        
    Raises:
        HTTPException: 404 if lead not found
        HTTPException: 500 on internal errors
    """
    try:
        lead = await db.get(Lead, lead_id)
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead with id {lead_id} not found"
            )
        return LeadResponse.model_validate(lead)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving lead: {str(e)}"
        )