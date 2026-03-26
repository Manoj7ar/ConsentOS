from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.accounts import router as accounts_router
from app.api.activity import router as activity_router
from app.api.approvals import router as approvals_router
from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.permissions import router as permissions_router
from app.api.token_vault import router as token_vault_router
from app.config import Settings, get_settings
from app.db import build_session_factory, init_db
from app.middleware.request_context import attach_request_context


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    session_factory, engine = build_session_factory(active_settings.database_url)
    init_db(engine)

    app = FastAPI(title=active_settings.app_name)
    app.state.settings = active_settings
    app.state.session_factory = session_factory
    app.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.middleware("http")(attach_request_context)

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(accounts_router)
    app.include_router(permissions_router)
    app.include_router(activity_router)
    app.include_router(token_vault_router)
    app.include_router(approvals_router)
    return app


app = create_app()

