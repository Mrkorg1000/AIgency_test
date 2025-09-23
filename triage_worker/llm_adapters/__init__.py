from llm_adapters.rule_based import RuleBasedLLM
from llm_adapters.base import BaseLLMAdapter
from common.config import settings

def get_llm_adapter() -> BaseLLMAdapter:
    """
    Factory for creating LLM adapters.
    Returns an adapter from the LLM_ADAPTER variable in config.
    """
    adapter_type = settings.LLM_ADAPTER.lower()
    
    if adapter_type == "rule_based":
        return RuleBasedLLM()
    else:
        return RuleBasedLLM()