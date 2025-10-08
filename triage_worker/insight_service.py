from common.schemas import InsightCreate
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional
from common.models import Insight


class InsightService:
    """Service for managing insights in the database."""
    
    async def create_insight(
        self, 
        session: AsyncSession, 
        insight_data: InsightCreate
    ) -> bool:
        """
        Creates an insight with idempotency check.
        
        Args:
            session: Database session
            insight_data: Insight data to create
            
        Returns:
            bool: True if created, False if duplicate
        """
        # Check for duplicate
        exists = await self.insight_exists(session, insight_data.lead_id, insight_data.content_hash)
        if exists:
            return False
            
        # Create and save insight
        try:
            insight = Insight(**insight_data.dict())
            session.add(insight)
            await session.commit()
            return True
        except Exception as e:
            await session.rollback()
            return False
    
    async def insight_exists(
        self, 
        session: AsyncSession, 
        lead_id: UUID, 
        content_hash: str
    ) -> bool:
        """
        Checks if insight exists for given lead_id + content_hash pair.
        
        Args:
            session: Database session
            lead_id: Lead UUID
            content_hash: Content hash for duplicate detection
            
        Returns:
            bool: True if insight exists, False otherwise
        """
        from sqlalchemy import select
        stmt = select(Insight).where(
            (Insight.lead_id == lead_id) &
            (Insight.content_hash == content_hash)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None