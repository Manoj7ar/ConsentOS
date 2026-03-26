from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="MCP_", extra="ignore", populate_by_name=True)

    backend_base_url: str = "http://localhost:8000"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    gemini_api_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    approval_timeout_seconds: int = 120
    approval_poll_interval_seconds: int = 2
    internal_api_shared_secret: str = Field(default="change-me", validation_alias="INTERNAL_API_SHARED_SECRET")
    gmail_api_base_url: str = "https://gmail.googleapis.com/gmail/v1"
    gmail_recent_query: str = 'newer_than:90d (invoice OR payment OR overdue OR "past due")'
    gmail_recent_limit: int = 50
    calendar_api_base_url: str = "https://www.googleapis.com/calendar/v3"
    calendar_id: str = "primary"
    calendar_lookahead_days: int = 30
    calendar_recent_limit: int = 10
    github_api_base_url: str = "https://api.github.com"
    stripe_api_base_url: str = "https://api.stripe.com/v1"
    stripe_recent_limit: int = 10
    stripe_default_currency: str = "usd"
    slack_api_base_url: str = "https://slack.com/api"
    slack_recent_limit: int = 25
    slack_mention_channel_ids: list[str] = Field(default_factory=list)
    slack_mention_keywords: list[str] = Field(
        default_factory=lambda: ["invoice", "payment", "paid", "overdue", "follow up", "follow-up"]
    )


@lru_cache
def get_settings() -> MCPSettings:
    return MCPSettings()
