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
    Redis Streams message handler.
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
            # 1. Validate and parse message
            event = await self._validate_message(message_data)
            
            # 2. Check for duplicates (idempotency)
            if await self._check_duplicate(event):
                return True  # Duplicate - skip processing
                
            # 3. Analyze note via LLM
            llm_response = await self._analyze_note(event)
            
            # 4. Save insight to database
            await self._save_insight(event, llm_response)
            
            return True  # Success
            
        except DuplicateInsightError as e:
            return True  # Duplicate - already processed
        except ValidationError as e:
            return False  # Invalid message
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False  # Any other error

    async def _validate_message(self, message_data: Dict[str, Any]) -> LeadEvent:
        """
        Validates and parses raw message into Pydantic model.
        
        Args:
            message_data: Raw message data from Redis
            
        Returns:
            LeadEvent: Validated lead event
            
        Raises:
            ValidationError: If message data is invalid
        """
        # Redis Streams may return all values as strings
        # Pydantic will handle UUID and datetime conversion
        return LeadEvent(**message_data)

    async def _check_duplicate(self, event: LeadEvent) -> bool:
        """
        Checks if insight already exists for this event.
        
        Args:
            event: Lead event to check
            
        Returns:
            bool: True if insight exists, False otherwise
        """
        return await self.insight_service.insight_exists(
            self.db_session, event.lead_id, event.content_hash
        )

    async def _analyze_note(self, event: LeadEvent) -> LLMResponse:
        """
        Analyzes note via LLM adapter.
        
        Args:
            event: Lead event with note to analyze
            
        Returns:
            LLMResponse: Analysis results
        """
        llm_request = LLMRequest(note=event.note)
        return await self.llm_adapter.triage(llm_request)

    async def _save_insight(self, event: LeadEvent, llm_response: LLMResponse):
        """
        Saves insight to database.
        
        Args:
            event: Lead event
            llm_response: LLM analysis results
            
        Raises:
            DuplicateInsightError: If insight creation failed (possible duplicate)
        """
        insight_data = InsightCreate(
            lead_id=event.lead_id,
            content_hash=event.content_hash,
            intent=llm_response.intent,
            priority=llm_response.priority,
            next_action=llm_response.next_action,
            confidence=llm_response.confidence,
            tags=llm_response.tags
        )
        
        success = await self.insight_service.create_insight(
            session=self.db_session,
            insight_data=insight_data
        )
        
        if not success:
            raise DuplicateInsightError("Failed to create insight - possible duplicate")