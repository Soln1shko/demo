from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FeedItemOut(BaseModel):
    id: str
    kind: str
    title: str
    body: str
    icon: str
    cta: dict[str, Any]
    reason: str


class FeedOut(BaseModel):
    profile: str
    items: list[FeedItemOut]


class FeedExplainOut(BaseModel):
    profile: str
    profile_label: str
    goal: str
    applications: int
    active_rules: list[str]


class FeedItemIn(BaseModel):
    id: str = Field(min_length=1, max_length=40)
    kind: str = "editorial"
    title: str = Field(max_length=160)
    body: str = Field(max_length=600)
    icon: str = "radio"
    cta: dict[str, Any] = Field(default_factory=dict)
    conditions: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    active: bool = True


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    text: str
    product_card: dict[str, Any] | None = None
    at: datetime


class ConversationOut(BaseModel):
    id: str
    greeting: str
    quick_questions: list[str]
    messages: list[MessageOut]
    ticket_id: str | None = None


class AskIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    organization_id: str | None = None
    application_id: str | None = None


class EscalateIn(BaseModel):
    application_id: str | None = None


class AnswerOut(BaseModel):
    user: MessageOut
    assistant: MessageOut | None = None
    source: str  # ml | llm | rules | operator


class TicketMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_role: str
    author_name: str
    text: str
    at: datetime


class TicketOut(BaseModel):
    id: str
    company: str
    application_id: str | None
    question: str
    status: str
    created_at: datetime
    messages: list[TicketMessageOut]


class TicketMessageIn(BaseModel):
    text: str = Field(min_length=3, max_length=1000)


class TicketPatch(BaseModel):
    status: str = Field(pattern="^(open|closed)$")


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    title: str
    payload: dict[str, Any]
    read_at: datetime | None
    created_at: datetime
