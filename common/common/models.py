from datetime import datetime
# from enum import Enum
from uuid import UUID, uuid4
from typing import List, Optional, Annotated
from sqlalchemy import JSON, Float, ForeignKey, String, Text, UniqueConstraint, text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase

from common.enums import IntentEnum, NextActionEnum, PriorityEnum

uuid_pk = Annotated[UUID, mapped_column(primary_key=True, default=uuid4)]
created_dt = Annotated[
    datetime,
    mapped_column(server_default=text("TIMEZONE('utc', now())")),
]

class Base(DeclarativeBase):
    pass

class Lead(Base):
    __tablename__ = "leads"
    
    id: Mapped[uuid_pk]
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[created_dt]


class Insight(Base):
    __tablename__ = "insights"
    
    id: Mapped[uuid_pk]
    lead_id: Mapped[UUID] = mapped_column(ForeignKey("leads.id"), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    
    intent: Mapped[IntentEnum] = mapped_column(SQLEnum(IntentEnum))
    priority: Mapped[PriorityEnum] = mapped_column(SQLEnum(PriorityEnum))
    next_action: Mapped[NextActionEnum] = mapped_column(SQLEnum(NextActionEnum))
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    tags: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[created_dt]
    __table_args__ = (UniqueConstraint('lead_id', 'content_hash', name='uq_lead_content'),)