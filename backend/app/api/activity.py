from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_current_user, get_db
from app.schemas.activity import ActivityCreate, ActivityListResponse, ActivityRead, ActivityUpdate
from app.schemas.auth import AuthenticatedUser
from app.services.activity_service import ActivityService

router = APIRouter(prefix="/api/activity", tags=["activity"])


@router.get("", response_model=ActivityListResponse)
def list_activity(current_user: AuthenticatedUser = Depends(get_current_user), db=Depends(get_db)) -> ActivityListResponse:
    return ActivityListResponse(items=ActivityService(db).list_activity(current_user.id))


@router.post("", response_model=ActivityRead)
def create_activity(
    payload: ActivityCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db=Depends(get_db),
) -> ActivityRead:
    return ActivityService(db).create(current_user.id, payload)


@router.patch("/{activity_id}", response_model=ActivityRead)
def update_activity(
    activity_id: int,
    payload: ActivityUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
    db=Depends(get_db),
) -> ActivityRead:
    return ActivityService(db).update(current_user.id, activity_id, payload)

