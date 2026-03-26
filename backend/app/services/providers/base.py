from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class ConnectionMetadata:
    external_user_id: str
    scopes: list[str]


class ProviderAdapter(Protocol):
    provider: str

    def default_scopes(self) -> list[str]:
        ...

    def connect(self, auth0_sub: str) -> ConnectionMetadata:
        ...

