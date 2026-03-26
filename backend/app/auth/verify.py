from __future__ import annotations

from typing import Any

import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient

from app.config import Settings

INTERNAL_SECRET_HEADER = "x-consentos-internal-secret"
USER_SUB_HEADER = "x-consentos-user-sub"
USER_EMAIL_HEADER = "x-consentos-user-email"
SUBJECT_TOKEN_HEADER = "x-consentos-auth0-subject-token"
DEV_SUB_HEADER = "x-dev-user-sub"
DEV_EMAIL_HEADER = "x-dev-user-email"


def _resolve_internal_identity(request: Request, settings: Settings) -> dict[str, Any] | None:
    if not settings.has_valid_internal_api_shared_secret:
        return None
    if request.headers.get(INTERNAL_SECRET_HEADER) != settings.internal_api_shared_secret:
        return None
    user_sub = request.headers.get(USER_SUB_HEADER)
    if not user_sub:
        return None
    return {
        "sub": user_sub,
        "email": request.headers.get(USER_EMAIL_HEADER),
        "subject_token": request.headers.get(SUBJECT_TOKEN_HEADER),
    }


def _resolve_dev_identity(request: Request, settings: Settings) -> dict[str, Any] | None:
    if not settings.allow_dev_auth_headers:
        return None
    user_sub = request.headers.get(DEV_SUB_HEADER)
    if not user_sub:
        return None
    return {"sub": user_sub, "email": request.headers.get(DEV_EMAIL_HEADER)}


def _verify_bearer_token(token: str, settings: Settings) -> dict[str, Any]:
    if not settings.auth0_base_url or not settings.auth0_audience:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Auth0 access token verification is not configured.",
        )
    jwk_client = PyJWKClient(f"{settings.auth0_base_url}/.well-known/jwks.json")
    signing_key = jwk_client.get_signing_key_from_jwt(token)
    issuer = settings.auth0_issuer or f"{settings.auth0_base_url}/"
    try:
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.auth0_audience,
            issuer=issuer,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid access token: {exc}",
        ) from exc


def resolve_identity(request: Request, settings: Settings) -> tuple[dict[str, Any], str | None]:
    internal_identity = _resolve_internal_identity(request, settings)
    if internal_identity:
        return internal_identity, internal_identity.get("subject_token")

    authorization = request.headers.get("authorization", "")
    if authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        return _verify_bearer_token(token, settings), token

    dev_identity = _resolve_dev_identity(request, settings)
    if dev_identity:
        return dev_identity, None

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing authenticated identity.")
