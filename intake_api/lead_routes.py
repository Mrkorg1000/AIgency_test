from datetime import datetime
import hashlib
import json
import uuid
from fastapi import APIRouter, Depends, HTTPException, Header, status
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from common.database import get_async_session
from intake_api.dependencies import get_redis, verify_idempotency_key
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
    Requires the Idempotency-Key header.
    """
    try:
        # Checking idempotency
        is_duplicate, cached_data = await verify_idempotency_key(
            redis, 
            idempotency_key,
            lead_data.dict()
        )
        
        if is_duplicate:
            # retreiving data from cash
            return JSONResponse(
                content=cached_data["response_data"],
                status_code=cached_data["status_code"]
            )
        
        # Creating Lead in DB
        lead = Lead(**lead_data.dict())
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
        
        # Preparing data for cashing
        cache_payload = {
            "status_code": status.HTTP_201_CREATED,
            "response_data": LeadResponse.from_orm(lead).dict(),
            "request_data": lead_data.dict()  # Сохраняем для будущих проверок
        }
        
        # Saving to Redis
        await redis.setex(
            f"idempotency:{idempotency_key}",
            86400,  # 24 часа
            json.dumps(cache_payload)
        )
        
        # Publishing an event to queue (for triage worker)
        await redis.xadd("lead_events", {
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
    Retreive Lead by UUID.
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