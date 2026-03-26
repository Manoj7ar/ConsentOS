from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BACKEND_",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "ConsentOS API"
    environment: str = "development"
    database_url: str = "sqlite:///./consentos.db"
    frontend_url: str = "http://localhost:3000"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    connected_accounts_stale_after_minutes: int = 1440

    auth0_domain: str | None = None
    auth0_audience: str | None = None
    auth0_issuer: str | None = None
    auth0_client_id: str | None = None
    auth0_client_secret: str | None = None
    auth0_ciba_client_id: str | None = None
    auth0_ciba_client_secret: str | None = None
    auth0_ciba_scope: str = "openid profile email"
    auth0_ciba_requested_expiry: int = 300
    auth0_connected_accounts_scope: str = "read:me:connected_accounts create:me:connected_accounts"

    google_connection_name: str = "google-oauth2"
    github_connection_name: str = "github"
    stripe_connection_name: str = "stripe"
    slack_connection_name: str = "slack"

    allow_dev_auth_headers: bool = False
    allow_mock_connected_accounts: bool = False
    allow_mock_token_vault: bool = False
    auto_approve_when_ciba_unavailable: bool = False
    auto_approve_delay_seconds: int = 2

    internal_api_shared_secret: str = Field(default="change-me", validation_alias="INTERNAL_API_SHARED_SECRET")

    def connection_name(self, provider: str) -> str:
        mapping = {
            "google": self.google_connection_name,
            "github": self.github_connection_name,
            "stripe": self.stripe_connection_name,
            "slack": self.slack_connection_name,
        }
        return mapping[provider]

    def provider_for_connection(self, connection_name: str) -> str | None:
        mapping = {
            self.google_connection_name: "google",
            self.github_connection_name: "github",
            self.stripe_connection_name: "stripe",
            self.slack_connection_name: "slack",
        }
        return mapping.get(connection_name)

    def default_provider_scopes(self, provider: str) -> list[str]:
        mapping = {
            "google": ["gmail.readonly", "gmail.send", "calendar.readonly", "calendar.events"],
            "github": ["repo", "read:user"],
            "stripe": ["customers.read", "payment_links.write", "payments.read"],
            "slack": ["channels:history", "chat:write", "users:read"],
        }
        return mapping[provider]

    @property
    def auth0_base_url(self) -> str | None:
        if not self.auth0_domain:
            return None
        return f"https://{self.auth0_domain}"

    @property
    def auth0_my_account_audience(self) -> str | None:
        if not self.auth0_base_url:
            return None
        return f"{self.auth0_base_url}/me/"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def strict_live_mode(self) -> bool:
        return not (
            self.allow_dev_auth_headers
            or self.allow_mock_connected_accounts
            or self.allow_mock_token_vault
            or self.auto_approve_when_ciba_unavailable
        )

    @property
    def has_valid_internal_api_shared_secret(self) -> bool:
        return bool(self.internal_api_shared_secret and self.internal_api_shared_secret != "change-me")


@lru_cache
def get_settings() -> Settings:
    return Settings()
