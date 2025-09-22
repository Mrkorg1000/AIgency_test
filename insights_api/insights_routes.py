from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from common.database import get_async_session
from common.models import Insight
from common.schemas import InsightResponse


insights_router = APIRouter(
    prefix="/leads",
    tags=["insights"],
)


@insights_router.get(
    "/{id}/insight",
    response_model=InsightResponse,
    status_code=status.HTTP_200_OK,
    responses={
        404: {"description": "Insight not found for the lead"},
    }
)
async def get_insight_by_lead_id(
    id: str,
    session: AsyncSession = Depends(get_async_session)
) -> InsightResponse:
    """
    Получает инсайт по идентификатору лида.
    """
    # Простой запрос - ищем любой инсайт для этого lead_id
    stmt = select(Insight).where(Insight.lead_id == id)
    
    result = await session.execute(stmt)
    insight = result.scalar_one_or_none()
    
    if not insight:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Insight not found for lead ID: {id}"
        )
    
    return InsightResponse.model_validate(insight)