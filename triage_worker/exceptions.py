class TriageWorkerError(Exception):
    """Базовая ошибка triage-worker"""
    pass

class DuplicateInsightError(TriageWorkerError):
    """Ошибка при попытке создать дубликат инсайта"""
    pass

class LLMServiceError(TriageWorkerError):
    """Ошибка при вызове LLM сервиса"""
    pass

class MessageProcessingError(TriageWorkerError):
    """Ошибка обработки сообщения из очереди"""
    pass

class DatabaseError(TriageWorkerError):
    """Ошибка работы с базой данных"""
    pass