from typing import Annotated, Any

from fastapi import APIRouter, Query, Response

from app.api.v1.common import CurrentOrg
from app.core.deps import Admin, Client, Session
from app.schemas.support import FeedExplainOut, FeedItemIn, FeedOut
from app.services import feed as svc

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("", response_model=FeedOut)
async def feed(
    org: CurrentOrg,
    session: Session,
    profile: Annotated[str | None, Query(pattern="^(retail|production|services)$")] = None,
    limit: Annotated[int, Query(ge=1, le=30)] = 10,
):
    return await svc.get_feed(session, org, limit, profile)


@router.get("/explain", response_model=FeedExplainOut)
async def explain(org: CurrentOrg, session: Session):
    return await svc.explain(session, org)


@router.get("/next-step")
async def next_step(org: CurrentOrg, session: Session) -> dict[str, Any]:
    return await svc.next_step(session, org)


@router.post("/restore", status_code=204)
async def restore(org: CurrentOrg, session: Session):
    await svc.restore_all(session, org)
    return Response(status_code=204)


@router.get("/items")
async def items(_: Admin, session: Session) -> list[dict[str, Any]]:
    return await svc.editorial(session)


@router.post("/items")
async def upsert_item(body: FeedItemIn, _: Admin, session: Session) -> dict[str, Any]:
    row = await svc.upsert_item(session, body)
    return svc.to_dict(row)


@router.post("/{item_id}/dismiss", status_code=204)
async def dismiss(item_id: str, org: CurrentOrg, session: Session, _: Client):
    await svc.dismiss(session, org, item_id)
    return Response(status_code=204)
