from __future__ import annotations

from pydantic import BaseModel


class WriteControlResponse(BaseModel):
    enabled: bool
    detail: str


class WriteControlUpdateRequest(BaseModel):
    enabled: bool


class ReceiptIntegritySummary(BaseModel):
    status: str
    checked_records: int
    broken_record_ids: list[int]
    latest_receipt_hash: str | None = None
    detail: str

