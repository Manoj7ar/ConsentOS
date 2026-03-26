from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import Settings
from app.deps import get_current_user, get_db, get_settings
from app.schemas.accounts import (
    ConnectAccountResponse,
    ConnectedAccountRead,
    SyncConnectedAccountsRequest,
    SyncConnectedAccountsResponse,
)
from app.schemas.auth import AuthenticatedUser
from app.services.connected_accounts_service import ConnectedAccountsService

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("", response_model=list[ConnectedAccountRead])
def list_accounts(
    current_user: AuthenticatedUser = Depends(get_current_user),
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> list[ConnectedAccountRead]:
    return ConnectedAccountsService(db, settings=settings).list_accounts(current_user.id)


@router.post("/connect/{provider}", response_model=ConnectAccountResponse)
def connect_account(
    provider: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ConnectAccountResponse:
    return ConnectedAccountsService(db, settings=settings).connect(current_user.id, current_user.auth0_sub, provider)


@router.post("/sync", response_model=SyncConnectedAccountsResponse)
def sync_accounts(
    payload: SyncConnectedAccountsRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db=Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SyncConnectedAccountsResponse:
    items = ConnectedAccountsService(db, settings=settings).sync(current_user.id, payload)
    return SyncConnectedAccountsResponse(items=items)
