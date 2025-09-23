from abc import ABC, abstractmethod
from common.schemas import LLMRequest, LLMResponse

class BaseLLMAdapter(ABC):
    """Abstract base class for all LLM adapters"""
    
    @abstractmethod
    async def triage(self, request: LLMRequest) -> LLMResponse:
        """
        Analyzes the lead’s note and returns a structured insight.
        
        Args:
            request: LLMRequest with note
            
        Returns:
            LLMResponse с intent, priority, next_action, confidence, tags
            
        Raises:
            LLMServiceError: In case of processing errors
        """
        pass