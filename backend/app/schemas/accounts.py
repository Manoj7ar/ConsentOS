from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ConnectedAccountRead(BaseModel):
    id: int
    provider: str
    external_user_id: str
    scopes: list[str]
    is_connected: bool
    connection_status: str
    status_detail: str | None = None
    last_synced_at: datetime | None = None
    auth0_created_at: datetime | None = None
    auth0_expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ConnectAccountResponse(BaseModel):
    account: ConnectedAccountRead | None = None
    provider: str
    status: str
    detail: str | None = None


class Auth0ConnectedAccountSyncItem(BaseModel):
    id: str
    connection: str
    scopes: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    expires_at: datetime | None = None


class SyncConnectedAccountsRequest(BaseModel):
    accounts: list[Auth0ConnectedAccountSyncItem] = Field(default_factory=list)


class SyncConnectedAccountsResponse(BaseModel):
    items: list[ConnectedAccountRead]
