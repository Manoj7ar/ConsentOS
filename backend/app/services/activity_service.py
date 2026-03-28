from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.repositories.activity_log import ActivityLogRepository
from app.schemas.activity import (
    ActivityCreate,
    ActivityIntegrityCheckResponse,
    ActivityMeta,
    ActivityRead,
    ActivityUpdate,
)


@dataclass(slots=True)
class _ReceiptMaterial:
    payload_hash: str
    prev_hash: str | None
    receipt_hash: str


class ActivityService:
    def __init__(self, session: Session):
        self.repo = ActivityLogRepository(session)
        self._secret = get_settings().internal_api_shared_secret

    def list_activity(self, user_id: int) -> list[ActivityRead]:
        return [self._to_read_model(record) for record in self.repo.list_for_user(user_id)]

    def create(self, user_id: int, payload: ActivityCreate, *, request_id: str | None = None) -> ActivityRead:
        material = self._materialize_receipt(
            user_id=user_id,
            agent_name=payload.agent_name,
            provider=payload.provider,
            tool_name=payload.tool_name,
            action=payload.action,
            status=payload.status,
            authorization_request_id=payload.authorization_request_id,
            input_payload=payload.input,
        )
        record = self.repo.create(
            user_id=user_id,
            agent_name=payload.agent_name,
            provider=payload.provider,
            tool_name=payload.tool_name,
            action=payload.action,
            input=payload.input,
            status=payload.status,
            authorization_request_id=payload.authorization_request_id,
            request_id=request_id,
            receipt_hash=material.receipt_hash,
            receipt_prev_hash=material.prev_hash,
            receipt_payload_hash=material.payload_hash,
        )
        return self._to_read_model(record)

    def update(self, user_id: int, activity_id: int, payload: ActivityUpdate) -> ActivityRead:
        record = self.repo.get_for_user(user_id, activity_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found.")
        updated = self.repo.update(
            record,
            status=payload.status,
            authorization_request_id=payload.authorization_request_id,
        )
        return self._to_read_model(updated)

    def get(self, user_id: int, activity_id: int):
        record = self.repo.get_for_user(user_id, activity_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found.")
        return record

    def update_input(self, user_id: int, activity_id: int, input_payload: dict) -> ActivityRead:
        record = self.repo.get_for_user(user_id, activity_id)
        if record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found.")
        updated = self.repo.update_input(record, input_payload=input_payload)
        return self._to_read_model(updated)

    def verify_integrity(self, user_id: int) -> ActivityIntegrityCheckResponse:
        records = self.repo.list_for_user_chronological(user_id)
        previous_hash: str | None = None
        broken_record_ids: list[int] = []
        valid = 0

        for record in records:
            expected_payload_hash = self._payload_hash(
                record.user_id,
                record.agent_name,
                record.provider,
                record.tool_name,
                record.action,
                record.status,
                record.authorization_request_id,
                record.input,
            )
            expected_receipt_hash = self._receipt_hash(expected_payload_hash, previous_hash)
            chain_link_ok = record.receipt_prev_hash == previous_hash
            hash_ok = record.receipt_payload_hash == expected_payload_hash and record.receipt_hash == expected_receipt_hash
            if chain_link_ok and hash_ok:
                valid += 1
            else:
                broken_record_ids.append(record.id)
            previous_hash = record.receipt_hash

        checked = len(records)
        invalid = len(broken_record_ids)
        status_value = "ok" if invalid == 0 else "tampered"
        detail = (
            "Receipt chain is valid."
            if invalid == 0
            else "Receipt chain mismatch detected. Activity history may have been modified."
        )
        return ActivityIntegrityCheckResponse(
            status=status_value,
            checked_records=checked,
            broken_record_ids=broken_record_ids,
            latest_receipt_hash=records[-1].receipt_hash if records else None,
            detail=detail,
        )

    def _materialize_receipt(
        self,
        *,
        user_id: int,
        agent_name: str,
        provider: str,
        tool_name: str,
        action: str,
        status: str,
        authorization_request_id: str | None,
        input_payload: dict,
    ) -> _ReceiptMaterial:
        prev_hash = self.repo.latest_hash_for_user(user_id)
        payload_hash = self._payload_hash(
            user_id,
            agent_name,
            provider,
            tool_name,
            action,
            status,
            authorization_request_id,
            input_payload,
        )
        receipt_hash = self._receipt_hash(payload_hash, prev_hash)
        return _ReceiptMaterial(payload_hash=payload_hash, prev_hash=prev_hash, receipt_hash=receipt_hash)

    def _payload_hash(
        self,
        user_id: int,
        agent_name: str,
        provider: str,
        tool_name: str,
        action: str,
        status: str,
        authorization_request_id: str | None,
        input_payload: dict,
    ) -> str:
        canonical_input = json.dumps(input_payload, sort_keys=True, separators=(",", ":"), default=str)
        payload = "|".join(
            [
                str(user_id),
                agent_name,
                provider,
                tool_name,
                action,
                status,
                authorization_request_id or "",
                canonical_input,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _receipt_hash(self, payload_hash: str, previous_hash: str | None) -> str:
        message = f"{payload_hash}|{previous_hash or ''}".encode("utf-8")
        return hmac.new(self._secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

    @staticmethod
    def _to_read_model(record) -> ActivityRead:
        meta_payload = record.input.get("_consentos", {}) if isinstance(record.input, dict) else {}
        chain_valid = bool(record.receipt_hash and record.receipt_payload_hash)
        return ActivityRead(
            id=record.id,
            agent_name=record.agent_name,
            provider=record.provider,
            tool_name=record.tool_name,
            action=record.action,
            input=record.input,
            activity_meta=ActivityMeta(
                workflow_id=meta_payload.get("workflow_id"),
                workflow_run_id=meta_payload.get("workflow_run_id"),
                policy_decision=meta_payload.get("policy_decision"),
                approval_mode=meta_payload.get("approval_mode"),
                receipt_id=str(record.id),
                receipt_hash=record.receipt_hash,
                receipt_prev_hash=record.receipt_prev_hash,
                chain_verified=chain_valid,
                request_id=record.request_id,
            ),
            status=record.status,
            authorization_request_id=record.authorization_request_id,
            created_at=record.created_at,
            receipt_id=str(record.id),
            receipt_hash=record.receipt_hash,
            receipt_prev_hash=record.receipt_prev_hash,
            chain_valid=chain_valid,
            request_id=record.request_id,
        )
