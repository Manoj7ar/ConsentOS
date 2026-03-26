from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.auth0_client import Auth0Client
from app.repositories.connected_accounts import ConnectedAccountRepository
from app.schemas.auth import AuthenticatedUser
from app.schemas.token_vault import TokenExchangeResponse


class TokenVaultService:
    def __init__(self, session: Session, auth0_client: Auth0Client):
        self.accounts_repo = ConnectedAccountRepository(session)
        self.auth0_client = auth0_client

    async def exchange(
        self,
        *,
        user: AuthenticatedUser,
        provider: str,
        login_hint: str | None = None,
    ) -> TokenExchangeResponse:
        account = self.accounts_repo.get_for_user_provider(user.id, provider)
        if account is None or not account.is_connected:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No connected account found for provider '{provider}'.",
            )
        if not user.raw_access_token and not self.auth0_client.settings.allow_mock_token_vault:
            raise HTTPException(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                detail=(
                    "A live Auth0 subject token is required for Token Vault exchange. "
                    "Call this endpoint through the trusted Next.js or MCP proxy that forwards the user token."
                ),
            )
        auth0_exchange = await self.auth0_client.exchange_connected_account_token(
            provider=provider,
            subject_token=user.raw_access_token,
            login_hint=login_hint,
        )
        if auth0_exchange:
            return TokenExchangeResponse(
                external_access_token=auth0_exchange["access_token"],
                expires_in=int(auth0_exchange.get("expires_in", 3600)),
                scope=auth0_exchange.get("scope", " ".join(account.scopes)),
                provider=provider,
                source="auth0-token-vault",
            )

        if not self.auth0_client.settings.allow_mock_token_vault:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "Auth0 Token Vault exchange failed. "
                    "Check Connected Accounts, Auth0 client credentials, and the forwarded user token."
                ),
            )

        mock_exchange = self.auth0_client.build_mock_exchange(provider, account.scopes)
        return TokenExchangeResponse(
            external_access_token=mock_exchange["access_token"],
            expires_in=mock_exchange["expires_in"],
            scope=mock_exchange["scope"],
            provider=provider,
            source=mock_exchange["source"],
        )
