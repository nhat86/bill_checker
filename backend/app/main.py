from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings

app = FastAPI(
    title="Grocery Receipt Auditor",
    description="API d'audit de tickets de caisse — promotions manquées et erreurs de facturation.",
    version="0.1.0",
)

# CORS: the Next.js frontend on :3000 may call this API on :8000.
# Restrictive on purpose — only our frontend origin, never "*".
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")
