from __future__ import annotations

from types import SimpleNamespace

import pytest

from consentos_mcp.servers import calendar_server, github_server, gmail_server, slack_server, stripe_server
from consentos_mcp.shared.auth_context import AgentContext
from consentos_mcp.shared.provider_http import ProviderApiError
from consentos_mcp.shared.settings import MCPSettings


CONTEXT = AgentContext(user_sub="auth0|test-user", email="demo@example.com")


@pytest.mark.anyio
async def test_fetch_recent_invoices_parses_live_gmail_payload(monkeypatch):
    async def fake_exchange_provider_access_token(**kwargs):
        return "google-token"

    async def fake_request_json(**kwargs):
        url = kwargs["url"]
        if url.endswith("/users/me/messages"):
            return {"messages": [{"id": "msg-1"}]}
        return {
            "snippet": "Outstanding amount: $1,200 due 2026-03-20.",
            "payload": {
                "headers": [
                    {"name": "From", "value": "Northwind <billing@northwind.studio>"},
                    {"name": "Subject", "value": "Invoice 1042 overdue"},
                    {"name": "Date", "value": "Tue, 18 Mar 2026 10:00:00 +0000"},
                ]
            },
        }

    monkeypatch.setattr(gmail_server, "exchange_provider_access_token", fake_exchange_provider_access_token)
    monkeypatch.setattr(gmail_server, "request_json", fake_request_json)
    monkeypatch.setattr(gmail_server, "get_settings", lambda: MCPSettings(gmail_recent_limit=5))

    invoices = await gmail_server.fetch_recent_invoices(CONTEXT)

    assert invoices[0]["client_email"] == "billing@northwind.studio"
    assert invoices[0]["subject"] == "Invoice 1042 overdue"
    assert invoices[0]["snippet"] == "Outstanding amount: $1,200 due 2026-03-20."


@pytest.mark.anyio
async def test_gmail_read_action_creates_failed_receipt(monkeypatch):
    async def fake_fetch_recent_invoices(context):
        raise ProviderApiError(provider="google", detail="token exchange failed")

    class FakeBackendClient:
        async def create_activity(self, *args, **kwargs):
            return {"id": 91}

    monkeypatch.setattr(gmail_server, "fetch_recent_invoices", fake_fetch_recent_invoices)
    monkeypatch.setattr(gmail_server, "BackendClient", lambda: FakeBackendClient())

    payload = await gmail_server.read_inbox_summary_action(CONTEXT)

    assert payload["status"] == "failed"
    assert payload["activity_log_id"] == 91
    assert "token exchange failed" in payload["detail"]


@pytest.mark.anyio
async def test_fetch_upcoming_meetings_parses_google_calendar(monkeypatch):
    async def fake_exchange_provider_access_token(**kwargs):
        return "google-token"

    async def fake_request_json(**kwargs):
        return {
            "items": [
                {
                    "id": "evt-1",
                    "summary": "Northwind renewal call",
                    "htmlLink": "https://calendar.google.com/event?eid=1",
                    "start": {"dateTime": "2026-03-27T10:30:00Z"},
                    "attendees": [{"email": "client1@northwind.studio"}],
                }
            ]
        }

    monkeypatch.setattr(calendar_server, "exchange_provider_access_token", fake_exchange_provider_access_token)
    monkeypatch.setattr(calendar_server, "request_json", fake_request_json)
    monkeypatch.setattr(calendar_server, "get_settings", lambda: MCPSettings(calendar_recent_limit=5))

    events = await calendar_server.fetch_upcoming_meetings(CONTEXT)

    assert events[0]["title"] == "Northwind renewal call"
    assert events[0]["time"] == "10:30"
    assert events[0]["attendees"] == ["client1@northwind.studio"]


@pytest.mark.anyio
async def test_fetch_open_issues_filters_pull_requests(monkeypatch):
    async def fake_exchange_provider_access_token(**kwargs):
        return "github-token"

    class FakeResponse:
        status_code = 200

        def json(self):
            return [
                {"number": 18, "title": "Need audit receipts export", "state": "open", "html_url": "https://github.com/i/18"},
                {
                    "number": 19,
                    "title": "PR placeholder",
                    "state": "open",
                    "html_url": "https://github.com/p/19",
                    "pull_request": {"url": "https://api.github.com/pulls/19"},
                },
            ]

    async def fake_request(**kwargs):
        return FakeResponse()

    monkeypatch.setattr(github_server, "exchange_provider_access_token", fake_exchange_provider_access_token)
    monkeypatch.setattr(github_server, "request", fake_request)

    issues = await github_server.fetch_open_issues(CONTEXT, "acme/consent-firewall")

    assert len(issues) == 1
    assert issues[0]["number"] == 18


@pytest.mark.anyio
async def test_fetch_recent_payments_parses_stripe_payment_intents(monkeypatch):
    async def fake_exchange_provider_access_token(**kwargs):
        return "stripe-token"

    async def fake_request_json(**kwargs):
        return {
            "data": [
                {"id": "pi_1", "amount": 240000, "currency": "usd", "status": "succeeded", "receipt_email": "ops@northwind.studio"}
            ]
        }

    monkeypatch.setattr(stripe_server, "exchange_provider_access_token", fake_exchange_provider_access_token)
    monkeypatch.setattr(stripe_server, "request_json", fake_request_json)

    payments = await stripe_server.fetch_recent_payments(CONTEXT)

    assert payments[0]["customer"] == "ops@northwind.studio"
    assert payments[0]["amount"] == "$2,400.00"
    assert payments[0]["status"] == "succeeded"


@pytest.mark.anyio
async def test_fetch_recent_mentions_filters_slack_messages(monkeypatch):
    async def fake_exchange_provider_access_token(**kwargs):
        return "slack-token"

    async def fake_request_json(**kwargs):
        url = kwargs["url"]
        if url.endswith("/auth.test"):
            return {"ok": True, "user_id": "U123"}
        if url.endswith("/conversations.history"):
            return {
                "ok": True,
                "messages": [
                    {"user": "U999", "text": "Can someone review the overdue invoice?", "ts": "1.0"},
                    {"user": "U555", "text": "Random status update", "ts": "2.0"},
                ],
            }
        if url.endswith("/users.info"):
            return {"ok": True, "user": {"real_name": "Ash"}}
        raise AssertionError(f"Unexpected Slack URL {url}")

    monkeypatch.setattr(slack_server, "exchange_provider_access_token", fake_exchange_provider_access_token)
    monkeypatch.setattr(slack_server, "request_json", fake_request_json)
    monkeypatch.setattr(
        slack_server,
        "get_settings",
        lambda: MCPSettings(slack_mention_channel_ids=["C123"], slack_recent_limit=10),
    )

    mentions = await slack_server.fetch_recent_mentions(CONTEXT)

    assert len(mentions) == 1
    assert mentions[0]["user"] == "Ash"
    assert "overdue invoice" in mentions[0]["text"].lower()
