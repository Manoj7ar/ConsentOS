from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.services.approval_service import ApprovalService


def test_persist_approval_window_anchors_to_now_not_activity_creation():
    """Delegated window must start when approval is granted, not when the activity row was created."""
    record = SimpleNamespace(
        status="approved",
        input={},
        id=99,
        created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    svc = MagicMock()
    svc.activity_service = MagicMock()
    ApprovalService._persist_approval_window(svc, 1, record, 30)
    call_kw = svc.activity_service.update_input.call_args
    assert call_kw[0][0] == 1
    assert call_kw[0][1] == 99
    payload = call_kw[0][2]
    approved_until = payload["_consentos"]["approved_until"]
    until = datetime.fromisoformat(approved_until)
    now = datetime.now(timezone.utc)
    assert until > now + timedelta(minutes=29)
    assert until < now + timedelta(minutes=31)
