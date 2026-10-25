from fastapi import APIRouter

from app.api.v1 import (
    applications,
    assistant,
    auth,
    bank,
    documents,
    feed,
    ml,
    organizations,
    products,
    system,
)

api_router = APIRouter()
for module in (auth, organizations, products, applications, documents, bank, feed, assistant, ml):
    api_router.include_router(module.router)
api_router.include_router(system.router)
api_router.include_router(system.internal)
