class TriageWorkerError(Exception):
    """Base exception for triage worker."""
    pass


class DuplicateInsightError(TriageWorkerError):
    """Raised when attempting to create a duplicate insight."""
    pass


class LLMServiceError(TriageWorkerError):
    """Raised when LLM service call fails."""
    pass


class MessageProcessingError(TriageWorkerError):
    """Raised when message processing from queue fails."""
    pass


class DatabaseError(TriageWorkerError):
    """Raised when database operation fails."""
    pass