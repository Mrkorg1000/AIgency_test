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
        exists = await self.insight_exists(session, insight_data.lead_id, insight_data.content_hash)
        print(f"[insight_service] insight_exists before create: {exists}")
        if exists:
            return False
            
        # Создаем и сохраняем инсайт
        try:
            print(f"[insight_service] Creating Insight ORM object with data={insight_data}")
            insight = Insight(**insight_data.dict())
            session.add(insight)
            await session.commit()
            print(f"[insight_service] Insight committed")
            return True
        except Exception as e:
            import traceback
            print(f"[insight_service] Error during commit: {e}")
            traceback.print_exc()
            await session.rollback()
            return False
    
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
        exists = result.scalar_one_or_none() is not None
        print(f"[insight_service] insight_exists query={exists}")
        return exists