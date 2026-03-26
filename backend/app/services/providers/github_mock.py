from __future__ import annotations

import hashlib

from app.services.providers.base import ConnectionMetadata


class GitHubMockProvider:
    provider = "github"

    def default_scopes(self) -> list[str]:
        return ["repo", "read:user"]

    def connect(self, auth0_sub: str) -> ConnectionMetadata:
        digest = hashlib.sha1(auth0_sub.encode("utf-8")).hexdigest()[:10]
        return ConnectionMetadata(external_user_id=f"github-user-{digest}", scopes=self.default_scopes())

