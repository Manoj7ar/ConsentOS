from __future__ import annotations

from fastapi import Depends, Request

from app.auth.auth0_client import Auth0Client
from app.auth.ciba import Auth0CIBAProvider
from app.auth.verify import resolve_identity
from app.config import Settings
from app.schemas.auth import AuthenticatedUser
from app.services.user_service import UserService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request):
    session = request.app.state.session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_auth0_client(settings: Settings = Depends(get_settings)) -> Auth0Client:
    return Auth0Client(settings)


def get_ciba_provider(request: Request, settings: Settings = Depends(get_settings)) -> Auth0CIBAProvider:
    provider = getattr(request.app.state, "ciba_provider", None)
    if provider is None:
        provider = Auth0CIBAProvider(settings)
        request.app.state.ciba_provider = provider
    return provider


def get_current_user(request: Request, settings: Settings = Depends(get_settings), db=Depends(get_db)) -> AuthenticatedUser:
    identity, raw_access_token = resolve_identity(request, settings)
    user = UserService(db).ensure_user(identity["sub"])
    return AuthenticatedUser(
        id=user.id,
        auth0_sub=user.auth0_sub,
        email=identity.get("email"),
        raw_access_token=raw_access_token,
        emergency_write_blocked=user.emergency_write_blocked,
    )
