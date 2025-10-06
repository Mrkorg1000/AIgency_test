from datetime import datetime
from uuid import UUID
from typing import List, Literal, Optional
from pydantic import BaseModel, EmailStr, Field

from common.enums import IntentEnum, NextActionEnum, PriorityEnum


class LeadBase(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    note: str
    source: Optional[str] = None


class LeadCreate(LeadBase):
    pass


class LeadResponse(LeadBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
        
        
# Lead.created scheme from redis queve
class LeadEvent(BaseModel):
    event_id: UUID
    type: Literal["lead.created"]
    lead_id: UUID
    note: str
    content_hash: str  # hash for idempotency check
    occurred_at: datetime
    
 
# LLM adapter Request
class LLMRequest(BaseModel):
    note: str
    
    

class LLMResponse(BaseModel):
    intent: IntentEnum
    priority: PriorityEnum
    next_action: NextActionEnum
    confidence: float = Field(ge=0.0, le=1.0)  # from 0.0 to 1.0
    tags: Optional[list[str]] = None
    
    
    
class InsightBase(BaseModel):
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
    pass


class InsightResponse(InsightBase):
    id: UUID
    created_at: datetime