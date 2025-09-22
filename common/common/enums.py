from enum import Enum


class IntentEnum(Enum):
    BUY = "buy"
    SUPPORT = "support"
    SPAM = "spam"
    JOB = "job"
    OTHER = "other"

class PriorityEnum(Enum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"

class NextActionEnum(Enum):
    CALL = "call"
    EMAIL = "email"
    IGNORE = "ignore"
    QUALIFY = "qualify"
