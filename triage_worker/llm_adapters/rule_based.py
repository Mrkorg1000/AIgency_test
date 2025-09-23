import re
from typing import Dict, List
from .base import BaseLLMAdapter
from common.schemas import LLMRequest, LLMResponse

class RuleBasedLLM(BaseLLMAdapter):
    """
    LLM адаптер на основе правил (keyword matching).
    Не требует внешних API вызовов, работает локально.
    """
    
    def __init__(self):
        # Словарь правил для определения intent
        self.intent_rules: Dict[str, Dict] = {
            'buy': {
                'keywords': ['цена', 'стоимость', 'купить', 'заказ', 'прайс', 'стоит', 'price', 'cost', 'buy'],
                'priority': 'P1'  # Дефолтный приоритет для intent
            },
            'support': {
                'keywords': ['помощь', 'сломал', 'ошибка', 'не работает', 'bug', 'help', 'support'],
                'priority': 'P2'
            },
            'job': {
                'keywords': ['вакансия', 'резюме', 'работа', 'карьера', 'job', 'career'],
                'priority': 'P3'
            },
            'spam': {
                'keywords': ['http://', 'https://', 'www.', '.com', 'реклама', 'spam'],
                'priority': 'P3'
            }
        }
        
        # Правила для определения приоритета
        self.priority_rules: Dict[str, List[str]] = {
            'P0': ['срочно', 'urgent', 'asap', 'немедленно', 'критично'],
            'P1': ['скоро', 'soon', 'ближайшее время', 'недолго'], 
            'P2': [],  # Базовый приоритет
            'P3': ['когда-нибудь', 'потом', 'не спеша']
        }
        
        # Маппинг intent + priority -> next_action
        self.action_rules: Dict[str, Dict[str, str]] = {
            'buy': {'P0': 'call', 'P1': 'email', 'P2': 'email', 'P3': 'qualify'},
            'support': {'P0': 'call', 'P1': 'email', 'P2': 'email', 'P3': 'email'},
            'job': {'P0': 'email', 'P1': 'email', 'P2': 'email', 'P3': 'ignore'},
            'spam': {'P0': 'ignore', 'P1': 'ignore', 'P2': 'ignore', 'P3': 'ignore'},
            'other': {'P0': 'qualify', 'P1': 'qualify', 'P2': 'qualify', 'P3': 'ignore'}
        }

    async def triage(self, request: LLMRequest) -> LLMResponse:
        """
        Анализирует заметку лида на основе ключевых слов.
        """
        note_lower = request.note.lower()
        
        # Определяем intent (намерение)
        intent = self._detect_intent(note_lower)
        
        # Определяем priority (приоритет)
        priority = self._detect_priority(note_lower, intent)
        
        # Определяем next_action (следующее действие)
        next_action = self._get_next_action(intent, priority)
        
        # Рассчитываем confidence (уверность)
        confidence = self._calculate_confidence(note_lower, intent)
        
        # Генерируем tags (теги)
        tags = self._generate_tags(note_lower)
        
        return LLMResponse(
            intent=intent,
            priority=priority,
            next_action=next_action,
            confidence=confidence,
            tags=tags
        )

    def _detect_intent(self, note: str) -> str:
        """
        Определяет intent на основе ключевых слов.
        Возвращает 'other' если не найден подходящий intent.
        """
        for intent, rules in self.intent_rules.items():
            if any(keyword in note for keyword in rules['keywords']):
                return intent
        return 'other'

    def _detect_priority(self, note: str, intent: str) -> str:
        """
        Определяет приоритет. Сначала ищет слова приоритета,
        если не находит - использует дефолтный для intent.
        """
        # Ищем слова приоритета в тексте
        for priority, keywords in self.priority_rules.items():
            if any(keyword in note for keyword in keywords):
                return priority
        
        # Используем дефолтный приоритет для intent
        return self.intent_rules.get(intent, {}).get('priority', 'P2')

    def _get_next_action(self, intent: str, priority: str) -> str:
        """
        Определяет следующее действие на основе intent и priority.
        """
        return self.action_rules.get(intent, {}).get(priority, 'qualify')

    def _calculate_confidence(self, note: str, intent: str) -> float:
        """
        Рассчитывает уверность в результате (0.0 - 1.0).
        """
        if intent == 'other':
            return 0.3  # Низкая уверность для other
        
        # Чем больше ключевых слов найдено, тем выше уверность
        keywords = self.intent_rules.get(intent, {}).get('keywords', [])
        matches = sum(1 for keyword in keywords if keyword in note)
        return min(0.3 + matches * 0.2, 0.9)  # От 0.3 до 0.9

    def _generate_tags(self, note: str) -> List[str]:
        """
        Генерирует дополнительные теги на основе содержимого.
        """
        tags = []
        if any(word in note for word in ['срочно', 'urgent', 'asap']):
            tags.append('urgent')
        if any(word in note for word in ['предприятие', 'бизнес', 'enterprise']):
            tags.append('enterprise')
        if any(word in note for word in ['пробный', 'trial', 'демо']):
            tags.append('trial')
        return tags