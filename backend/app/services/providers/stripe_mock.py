from __future__ import annotations

import hashlib

from app.services.providers.base import ConnectionMetadata


class StripeMockProvider:
    provider = "stripe"

    def default_scopes(self) -> list[str]:
        return ["customers.read", "payment_links.write", "payments.read"]

    def connect(self, auth0_sub: str) -> ConnectionMetadata:
        digest = hashlib.sha1(auth0_sub.encode("utf-8")).hexdigest()[:10]
        return ConnectionMetadata(external_user_id=f"stripe-account-{digest}", scopes=self.default_scopes())

