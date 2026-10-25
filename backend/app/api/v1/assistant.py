from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import Client, Session, get_user_org
from app.core.errors import not_found
from app.models import Application, AssistantConversation, AssistantMessage, SupportMessage, SupportTicket
from app.schemas.support import (
    AnswerOut,
    AskIn,
    ConversationOut,
    EscalateIn,
    TicketMessageIn,
    TicketOut,
)
from app.services import assistant as svc
from app.services import organizations as orgs

router = APIRouter(tags=["assistant"])


async def _own_conversation(session: Session, user: Client, conversation_id: str) -> AssistantConversation:
    conv = await session.get(AssistantConversation, conversation_id)
    if conv is None or conv.user_id != user.id:
        raise not_found("Диалог")
    return conv


@router.post("/assistant/conversations", response_model=ConversationOut)
async def open_conversation(user: Client, session: Session):
    return await svc.get_conversation(session, user, None)


@router.get("/assistant/conversations/{conversation_id}", response_model=ConversationOut)
async def get_conversation(conversation_id: str, user: Client, session: Session):
    await _own_conversation(session, user, conversation_id)
    return await svc.get_conversation(session, user, None)


@router.delete("/assistant/conversations/{conversation_id}", status_code=204)
async def clear_conversation(conversation_id: str, user: Client, session: Session):
    await _own_conversation(session, user, conversation_id)
    await svc.clear_conversation(session, user)


@router.post("/assistant/conversations/{conversation_id}/messages", response_model=AnswerOut)
async def ask(conversation_id: str, body: AskIn, user: Client, session: Session):
    await _own_conversation(session, user, conversation_id)
    return await svc.ask(session, user, body.text, body.organization_id, body.application_id)


@router.post("/assistant/conversations/{conversation_id}/escalate", response_model=TicketOut)
async def escalate(conversation_id: str, user: Client, session: Session, body: EscalateIn | None = None):
    conv = await _own_conversation(session, user, conversation_id)
    application_id = body.application_id if body else None
    org = None
    if application_id:
        app = await session.get(Application, application_id)
        if app is None:
            application_id = None
        else:
            org = await get_user_org(session, user, app.organization_id)
    open_ticket = next(
        (t for t in await svc.list_tickets(session, user, bank=False) if t.status != "closed"), None
    )
    if open_ticket is not None:
        if application_id and not open_ticket.application_id:
            row = await session.get(SupportTicket, open_ticket.id)
            if row is not None:
                row.application_id = application_id
                await session.commit()
            return await svc.get_ticket(session, user, False, open_ticket.id)
        return open_ticket
    if org is None:
        found = await orgs.list_orgs(session, user)
        org = found[0] if found else None
    if org is None:
        raise not_found("Организация")
    last = (
        await session.execute(
            select(AssistantMessage.text)
            .where(AssistantMessage.conversation_id == conv.id, AssistantMessage.role == "user")
            .order_by(AssistantMessage.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return await svc.create_ticket(
        session, user, org, last or "Нужна консультация оператора", application_id, conv.id
    )


@router.get("/support/tickets", response_model=list[TicketOut])
async def my_tickets(user: Client, session: Session):
    return await svc.list_tickets(session, user, bank=False)


@router.get("/support/tickets/{ticket_id}", response_model=TicketOut)
async def my_ticket(ticket_id: str, user: Client, session: Session):
    return await svc.get_ticket(session, user, False, ticket_id)


@router.post("/support/tickets/{ticket_id}/messages", response_model=TicketOut)
async def add_message(ticket_id: str, body: TicketMessageIn, user: Client, session: Session):
    t = await svc.get_ticket(session, user, False, ticket_id)
    session.add(
        SupportMessage(ticket_id=t.id, author_role="client", author_name=user.name, text=body.text.strip())
    )
    row = await session.get(SupportTicket, t.id)
    if row is not None and row.status != "closed":
        row.status = "open"
    await session.commit()
    return await svc.get_ticket(session, user, False, ticket_id)
