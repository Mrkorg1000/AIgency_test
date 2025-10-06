from typing import Dict, Any
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError
from common.schemas import InsightCreate, LLMResponse, LeadEvent, LLMRequest
from insight_service import InsightService
from llm_adapters import get_llm_adapter
from exceptions import DuplicateInsightError

class MessageProcessor:
    """
    Redis Streams Message handler.
    Responsible for converting raw messages into insights.
    """
    
    def __init__(self, redis: Redis, db_session: AsyncSession):
        self.redis = redis
        self.db_session = db_session
        self.llm_adapter = get_llm_adapter()
        self.insight_service = InsightService()

    async def process_message(self, message_data: Dict[str, Any]) -> bool:
        """
        Processes a single message from the queue.

        Args:
            message_data: Raw message data from Redis

        Returns:
            bool: True if the message was processed successfully,
            False if an error occurred
        """
        try:
            print(f"[processor] Start processing: {message_data}")
            # 1. Валидация и парсинг сообщения
            event = await self._validate_message(message_data)
            print(f"[processor] Parsed event: {event}")
            
            # 2. Проверка идемпотентности
            if await self._check_duplicate(event):
                print(f"[processor] Duplicate insight for lead_id={event.lead_id} content_hash={event.content_hash}")
                return True  # Дубликат - пропускаем
                
            # 3. Анализ заметки через LLM
            llm_response = await self._analyze_note(event)
            print(f"[processor] LLM response: {llm_response}")
            
            # 4. Сохранение инсайта в БД
            await self._save_insight(event, llm_response)
            print(f"[processor] Insight saved for lead_id={event.lead_id}")
            
            return True  # Успех
            
        except DuplicateInsightError as e:
            print(f"[processor] DuplicateInsightError: {e}")
            return True  # Дубликат - уже обработано
        except ValidationError as e:
            print(f"[processor] ValidationError while parsing message: {e}")
            return False  # Невалидное сообщение
        except Exception as e:
            import traceback
            print(f"[processor] Unexpected error while processing message: {e}")
            traceback.print_exc()
            return False  # Любая другая ошибка

    async def _validate_message(self, message_data: Dict[str, Any]) -> LeadEvent:
        """Валидирует и парсит сырое сообщение в Pydantic модель"""
        # Redis Streams может возвращать все значения как строки
        # Pydantic сам справится с UUID и datetime, но убедимся, что есть все поля
        return LeadEvent(**message_data)

    async def _check_duplicate(self, event: LeadEvent) -> bool:
        """Проверяет существует ли уже инсайт для этого события"""
        exists = await self.insight_service.insight_exists(
            self.db_session, event.lead_id, event.content_hash
        )
        print(f"[processor] insight_exists={exists}")
        return exists

    async def _analyze_note(self, event: LeadEvent) -> LLMResponse:
        """Анализирует заметку через LLM адаптер"""
        llm_request = LLMRequest(note=event.note)
        return await self.llm_adapter.triage(llm_request)

    async def _save_insight(self, event: LeadEvent, llm_response: LLMResponse):
        """Сохраняет инсайт в БД"""
        
        insight_data = InsightCreate(
            lead_id=event.lead_id,
            content_hash=event.content_hash,
            intent=llm_response.intent,
            priority=llm_response.priority,
            next_action=llm_response.next_action,
            confidence=llm_response.confidence,
            tags=llm_response.tags
        )
        print(f"[processor] Creating insight: {insight_data}")
        success = await self.insight_service.create_insight(
            session=self.db_session,
            insight_data=insight_data
        )
        print(f"[processor] create_insight success={success}")
        
        if not success:
            raise DuplicateInsightError("Failed to create insight - possible duplicate")