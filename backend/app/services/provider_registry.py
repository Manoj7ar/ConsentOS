from __future__ import annotations

from fastapi import HTTPException, status

from app.services.providers.github_mock import GitHubMockProvider
from app.services.providers.google_mock import GoogleMockProvider
from app.services.providers.slack_mock import SlackMockProvider
from app.services.providers.stripe_mock import StripeMockProvider


class ProviderRegistry:
    def __init__(self):
        self._providers = {
            "google": GoogleMockProvider(),
            "github": GitHubMockProvider(),
            "stripe": StripeMockProvider(),
            "slack": SlackMockProvider(),
        }

    def get(self, provider: str):
        try:
            return self._providers[provider]
        except KeyError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unsupported provider: {provider}",
            ) from exc

