from datetime import datetime
from uuid import UUID
from typing import List, Literal, Optional
from pydantic import BaseModel, EmailStr, Field

from common.enums import IntentEnum, NextActionEnum, PriorityEnum


class LeadBase(BaseModel):
    """Base schema for lead data."""
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    note: str
    source: Optional[str] = None


class LeadCreate(LeadBase):
    """Schema for creating a new lead."""
    pass


class LeadResponse(LeadBase):
    """Schema for lead API responses."""
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class LeadEvent(BaseModel):
    """Schema for lead.created events in Redis Stream."""
    event_id: UUID
    type: Literal["lead.created"]
    lead_id: UUID
    note: str
    content_hash: str  # SHA256 hash for duplicate detection
    occurred_at: datetime


class LLMRequest(BaseModel):
    """Request schema for LLM adapter."""
    note: str


class LLMResponse(BaseModel):
    """Response schema from LLM adapter."""
    intent: IntentEnum
    priority: PriorityEnum
    next_action: NextActionEnum
    confidence: float = Field(ge=0.0, le=1.0)  # Range: 0.0 to 1.0
    tags: Optional[List[str]] = None


class InsightBase(BaseModel):
    """Base schema for insight data."""
    lead_id: UUID
    content_hash: str
    intent: IntentEnum
    priority: PriorityEnum
    next_action: NextActionEnum
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    tags: Optional[List[str]] = None

    class Config:
        from_attributes = True


class InsightCreate(InsightBase):
    """Schema for creating a new insight."""
    pass


class InsightResponse(InsightBase):
    """Schema for insight API responses."""
    id: UUID
    created_at: datetime