from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from common.database import get_async_session
from common.models import Insight
from common.schemas import InsightResponse


insights_router = APIRouter(
    prefix="/leads",
    tags=["insights"],
)


@insights_router.get(
    "/{lead_id}/insight",
    response_model=InsightResponse,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Insight not found for the lead"},
    }
)
async def get_insight_by_lead_id(
    lead_id: UUID,
    session: AsyncSession = Depends(get_async_session)
) -> InsightResponse:
    """
    Retrieves insight by lead ID.
    
    Args:
        lead_id: UUID of the lead to get insight for
        session: Database session (injected)
        
    Returns:
        InsightResponse: The insight data for the lead
        
    Raises:
        HTTPException: 404 if no insight found for the lead
    """
    # Query for any insight matching this lead_id
    stmt = select(Insight).where(Insight.lead_id == lead_id)
    
    result = await session.execute(stmt)
    insight = result.scalar_one_or_none()
    
    if not insight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Insight not found for lead ID: {lead_id}"
        )
    
    return InsightResponse.model_validate(insight)