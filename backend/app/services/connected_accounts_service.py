from __future__ import annotations

from datetime import timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.user import utcnow
from app.repositories.connected_accounts import ConnectedAccountRepository
from app.schemas.accounts import (
    Auth0ConnectedAccountSyncItem,
    ConnectAccountResponse,
    ConnectedAccountRead,
    SyncConnectedAccountsRequest,
)
from app.services.provider_registry import ProviderRegistry


class ConnectedAccountsService:
    def __init__(
        self,
        session: Session,
        settings: Settings | None = None,
        registry: ProviderRegistry | None = None,
    ):
        self.repo = ConnectedAccountRepository(session)
        self.settings = settings or get_settings()
        self.registry = registry or ProviderRegistry()

    def list_accounts(self, user_id: int) -> list[ConnectedAccountRead]:
        now = utcnow()
        return [self._to_read_model(account, now=now) for account in self.repo.list_for_user(user_id)]

    def connect(self, user_id: int, auth0_sub: str, provider: str) -> ConnectAccountResponse:
        self._validate_provider(provider)
        if not self.settings.allow_mock_connected_accounts:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Direct backend account connection is disabled. Use the Next.js Auth0 connect flow instead.",
            )

        adapter = self.registry.get(provider)
        metadata = adapter.connect(auth0_sub)
        sync_time = utcnow()
        account = self.repo.upsert(
            user_id=user_id,
            provider=provider,
            external_user_id=metadata.external_user_id,
            scopes=metadata.scopes,
            is_connected=True,
            last_synced_at=sync_time,
            status_detail="Connected using the local mock provider flow.",
        )
        return ConnectAccountResponse(
            account=self._to_read_model(account, now=sync_time),
            provider=provider,
            status="connected",
            detail="Connected using the local mock provider flow.",
        )

    def sync(self, user_id: int, payload: SyncConnectedAccountsRequest) -> list[ConnectedAccountRead]:
        sync_time = utcnow()
        connected_providers: set[str] = set()
        for account in payload.accounts:
            provider = self._provider_for_sync_item(account)
            if provider is None:
                continue
            connected_providers.add(provider)
            scopes = account.scopes or self.settings.default_provider_scopes(provider)
            self.repo.upsert(
                user_id=user_id,
                provider=provider,
                external_user_id=account.id,
                scopes=scopes,
                is_connected=True,
                last_synced_at=sync_time,
                auth0_created_at=account.created_at,
                auth0_expires_at=account.expires_at,
                status_detail=None,
            )

        for existing in self.repo.list_for_user(user_id):
            if existing.provider not in connected_providers:
                existing.is_connected = False
                existing.last_synced_at = sync_time
                existing.status_detail = "No longer present in the latest Auth0 sync. Reconnect the account in Auth0 and sync again."

        return self.list_accounts(user_id)

    def _provider_for_sync_item(self, account: Auth0ConnectedAccountSyncItem) -> str | None:
        provider = self.settings.provider_for_connection(account.connection)
        if provider is not None:
            return provider
        for known_provider in ("google", "github", "stripe", "slack"):
            if account.connection.startswith(known_provider):
                return known_provider
        return None

    def _validate_provider(self, provider: str) -> None:
        try:
            self.settings.connection_name(provider)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unsupported provider: {provider}") from exc

    def _to_read_model(self, account, *, now) -> ConnectedAccountRead:
        connection_status = self._connection_status(account, now=now)
        return ConnectedAccountRead(
            id=account.id,
            provider=account.provider,
            external_user_id=account.external_user_id,
            scopes=account.scopes,
            is_connected=account.is_connected,
            connection_status=connection_status,
            status_detail=self._status_detail(account, connection_status),
            last_synced_at=account.last_synced_at,
            auth0_created_at=account.auth0_created_at,
            auth0_expires_at=account.auth0_expires_at,
            created_at=account.created_at,
            updated_at=account.updated_at,
        )

    def _connection_status(self, account, *, now) -> str:
        if not account.is_connected:
            return "disconnected"

        stale_after_minutes = self.settings.connected_accounts_stale_after_minutes
        if stale_after_minutes > 0:
            last_synced_at = self._coerce_utc(account.last_synced_at)
            if last_synced_at is None:
                return "stale"
            cutoff = now - timedelta(minutes=stale_after_minutes)
            if last_synced_at <= cutoff:
                return "stale"

        return "connected"

    def _status_detail(self, account, connection_status: str) -> str:
        if connection_status == "disconnected":
            return account.status_detail or "This account is not present in the latest Auth0 sync."
        if connection_status == "stale":
            return (
                account.status_detail
                or "Account metadata is stale. Run Sync from Auth0 to refresh the connected-account record."
            )
        return account.status_detail or "Connected and recently synced from Auth0."

    @staticmethod
    def _coerce_utc(value):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
