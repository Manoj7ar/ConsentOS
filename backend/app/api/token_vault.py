from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_auth0_client, get_current_user, get_db
from app.schemas.auth import AuthenticatedUser
from app.schemas.token_vault import TokenExchangeRequest, TokenExchangeResponse
from app.services.token_vault_service import TokenVaultService

router = APIRouter(prefix="/api/token-vault", tags=["token-vault"])


@router.post("/exchange", response_model=TokenExchangeResponse)
async def exchange_token(
    payload: TokenExchangeRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db=Depends(get_db),
    auth0_client=Depends(get_auth0_client),
) -> TokenExchangeResponse:
    return await TokenVaultService(db, auth0_client).exchange(
        user=current_user,
        provider=payload.provider,
        login_hint=payload.login_hint,
    )

