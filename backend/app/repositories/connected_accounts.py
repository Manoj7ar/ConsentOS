from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.connected_account import ConnectedAccount


class ConnectedAccountRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_for_user(self, user_id: int) -> list[ConnectedAccount]:
        return list(
            self.session.scalars(
                select(ConnectedAccount).where(ConnectedAccount.user_id == user_id).order_by(ConnectedAccount.provider)
            )
        )

    def get_for_user_provider(self, user_id: int, provider: str) -> ConnectedAccount | None:
        return self.session.scalar(
            select(ConnectedAccount).where(
                ConnectedAccount.user_id == user_id,
                ConnectedAccount.provider == provider,
            )
        )

    def upsert(
        self,
        *,
        user_id: int,
        provider: str,
        external_user_id: str,
        scopes: list[str],
        is_connected: bool = True,
        last_synced_at=None,
        auth0_created_at=None,
        auth0_expires_at=None,
        status_detail: str | None = None,
    ) -> ConnectedAccount:
        account = self.get_for_user_provider(user_id, provider)
        if account is None:
            account = ConnectedAccount(
                user_id=user_id,
                provider=provider,
                external_user_id=external_user_id,
                scopes=scopes,
                is_connected=is_connected,
                last_synced_at=last_synced_at,
                auth0_created_at=auth0_created_at,
                auth0_expires_at=auth0_expires_at,
                status_detail=status_detail,
            )
            self.session.add(account)
        else:
            account.external_user_id = external_user_id
            account.scopes = scopes
            account.is_connected = is_connected
            account.last_synced_at = last_synced_at
            account.auth0_created_at = auth0_created_at
            account.auth0_expires_at = auth0_expires_at
            account.status_detail = status_detail
        self.session.flush()
        return account
