from common.schemas import InsightCreate

from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Optional
from common.models import Insight


class InsightService:
    
    async def create_insight(
        self, 
        session: AsyncSession, 
        insight_data: InsightCreate
    ) -> bool:
        """
        Создает инсайт с проверкой идемпотентности.
        Возвращает True если создан, False если дубликат.
        """
        # Проверяем дубликат
        if await self.insight_exists(session, insight_data.lead_id, insight_data.content_hash):
            return False
            
        # Создаем и сохраняем инсайт
        insight = Insight(**insight_data.dict())
        session.add(insight)
        await session.commit()
        return True
    
    async def insight_exists(
        self, 
        session: AsyncSession, 
        lead_id: UUID, 
        content_hash: str
    ) -> bool:
        """Проверяет существует ли инсайт для данной пары lead_id + content_hash"""
        from sqlalchemy import select
        stmt = select(Insight).where(
            (Insight.lead_id == lead_id) &
            (Insight.content_hash == content_hash)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None