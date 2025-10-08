from enum import Enum


class IntentEnum(Enum):
    """Lead intent classification."""
    BUY = "buy"
    SUPPORT = "support"
    SPAM = "spam"
    JOB = "job"
    OTHER = "other"


class PriorityEnum(Enum):
    """Lead priority levels (P0 = highest, P3 = lowest)."""
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class NextActionEnum(Enum):
    """Recommended next action for lead."""
    CALL = "call"
    EMAIL = "email"
    IGNORE = "ignore"
    QUALIFY = "qualify"
