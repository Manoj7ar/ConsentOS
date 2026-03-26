from __future__ import annotations

import secrets
from typing import Any

import httpx

from app.config import Settings


class Auth0Client:
    def __init__(self, settings: Settings):
        self.settings = settings

    def can_exchange_connected_account_token(self) -> bool:
        return bool(self.settings.auth0_base_url and self.settings.auth0_client_id and self.settings.auth0_client_secret)

    async def exchange_connected_account_token(
        self,
        *,
        provider: str,
        subject_token: str | None,
        login_hint: str | None,
    ) -> dict[str, Any] | None:
        if not self.can_exchange_connected_account_token():
            return None
        if not subject_token:
            return None

        payload = {
            "grant_type": "urn:auth0:params:oauth:grant-type:token-exchange:federated-connection-access-token",
            "subject_token": subject_token,
            "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
            "requested_token_type": "http://auth0.com/oauth/token-type/federated-connection-access-token",
            "connection": self.settings.connection_name(provider),
        }
        if login_hint:
            payload["login_hint"] = login_hint

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.settings.auth0_base_url}/oauth/token",
                data=payload,
                auth=(self.settings.auth0_client_id, self.settings.auth0_client_secret),
            )
            if response.status_code >= 400:
                return None
            return response.json()

    async def list_connected_accounts(self, access_token: str) -> list[dict[str, Any]]:
        if not self.settings.auth0_base_url:
            return []

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{self.settings.auth0_base_url}/me/v1/connected-accounts",
                headers={"authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                return payload
            if isinstance(payload, dict):
                items = payload.get("connected_accounts")
                if isinstance(items, list):
                    return items
            return []

    def build_mock_exchange(self, provider: str, scopes: list[str]) -> dict[str, Any]:
        return {
            "access_token": f"{provider}_tv_{secrets.token_urlsafe(18)}",
            "expires_in": 3600,
            "scope": " ".join(scopes),
            "source": "mock-token-vault",
        }
