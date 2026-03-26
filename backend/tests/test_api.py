from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.repositories.connected_accounts import ConnectedAccountRepository
from app.models.user import utcnow
from app.services.auth0_diagnostics_service import Auth0DiagnosticsService


def test_health_ready_reports_degraded_when_auth0_missing(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert any(check["code"] == "auth0_discovery_unavailable" for check in payload["checks"])
    assert any(check["code"] == "mock_fallbacks_enabled" for check in payload["checks"])


def test_auth_diagnostics_requires_authenticated_user(client):
    response = client.get("/api/auth/diagnostics")
    assert response.status_code == 401


def test_sync_account_and_exchange_token(client, auth_headers):
    response = client.post(
        "/api/accounts/sync",
        headers=auth_headers,
        json={
            "accounts": [
                {
                    "id": "ca_google_123",
                    "connection": "google-oauth2",
                    "scopes": ["gmail.readonly", "gmail.send"],
                }
            ]
        },
    )
    assert response.status_code == 200
    account = response.json()["items"][0]
    assert account["provider"] == "google"
    assert "gmail.send" in account["scopes"]

    token_response = client.post(
        "/api/token-vault/exchange",
        headers=auth_headers,
        json={"provider": "google"},
    )
    assert token_response.status_code == 200
    payload = token_response.json()
    assert payload["provider"] == "google"
    assert payload["source"] in {"mock-token-vault", "auth0-token-vault"}
    assert account["connection_status"] == "connected"
    assert account["status_detail"] == "Connected and recently synced from Auth0."
    assert account["last_synced_at"] is not None


def test_sync_marks_missing_account_disconnected(client, auth_headers):
    first_sync = client.post(
        "/api/accounts/sync",
        headers=auth_headers,
        json={"accounts": [{"id": "ca_google_123", "connection": "google-oauth2", "scopes": ["gmail.send"]}]},
    )
    assert first_sync.status_code == 200

    second_sync = client.post(
        "/api/accounts/sync",
        headers=auth_headers,
        json={"accounts": []},
    )
    assert second_sync.status_code == 200
    payload = second_sync.json()
    account = payload["items"][0]
    assert account["provider"] == "google"
    assert account["connection_status"] == "disconnected"
    assert "latest Auth0 sync" in account["status_detail"]


def test_list_accounts_marks_old_sync_as_stale(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'stale.db'}"
    settings = Settings(
        database_url=database_url,
        cors_origins=["http://localhost:3000"],
        internal_api_shared_secret="test-secret",
        connected_accounts_stale_after_minutes=60,
        auto_approve_delay_seconds=0,
        auto_approve_when_ciba_unavailable=True,
    )
    app = create_app(settings)
    headers = {
        "x-consentos-internal-secret": "test-secret",
        "x-consentos-user-sub": "auth0|stale-user",
        "x-consentos-user-email": "stale@example.com",
    }

    with TestClient(app) as stale_client:
        sync_response = stale_client.post(
            "/api/accounts/sync",
            headers=headers,
            json={"accounts": [{"id": "ca_google_123", "connection": "google-oauth2", "scopes": ["gmail.send"]}]},
        )
        assert sync_response.status_code == 200

        with app.state.session_factory() as session:
            account = ConnectedAccountRepository(session).get_for_user_provider(1, "google")
            assert account is not None
            account.last_synced_at = utcnow() - timedelta(hours=2)
            session.commit()

        list_response = stale_client.get("/api/accounts", headers=headers)
        assert list_response.status_code == 200
        payload = list_response.json()[0]
        assert payload["connection_status"] == "stale"
        assert "stale" in payload["status_detail"].lower()


def test_mock_connect_endpoint_is_explicit(client, auth_headers):
    response = client.post("/api/accounts/connect/google", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "google"
    assert payload["status"] == "connected"
    assert payload["account"]["provider"] == "google"
    assert payload["account"]["connection_status"] == "connected"


def test_permission_override_and_risk_check(client, auth_headers):
    client.post(
        "/api/accounts/sync",
        headers=auth_headers,
        json={"accounts": [{"id": "ca_stripe_123", "connection": "stripe", "scopes": ["payment_links.write"]}]},
    )

    upsert = client.post(
        "/api/permissions",
        headers=auth_headers,
        json={
            "agent_name": "FreelanceCOOAgent",
            "provider": "stripe",
            "tool_name": "stripe:create_payment_link",
            "is_allowed": True,
            "risk_level": "high",
        },
    )
    assert upsert.status_code == 200
    risk = client.post(
        "/api/risk/require_approval",
        headers=auth_headers,
        json={
            "agent_name": "FreelanceCOOAgent",
            "provider": "stripe",
            "tool_name": "stripe:create_payment_link",
        },
    )
    assert risk.status_code == 200
    assert risk.json()["needs_approval"] is True


def test_stripe_payment_link_requires_approval_even_if_risk_lowered(client, auth_headers):
    client.post(
        "/api/accounts/sync",
        headers=auth_headers,
        json={"accounts": [{"id": "ca_stripe_123", "connection": "stripe", "scopes": ["payment_links.write"]}]},
    )
    upsert = client.post(
        "/api/permissions",
        headers=auth_headers,
        json={
            "agent_name": "FreelanceCOOAgent",
            "provider": "stripe",
            "tool_name": "stripe:create_payment_link",
            "is_allowed": True,
            "risk_level": "low",
        },
    )
    assert upsert.status_code == 200

    risk = client.post(
        "/api/risk/require_approval",
        headers=auth_headers,
        json={
            "agent_name": "FreelanceCOOAgent",
            "provider": "stripe",
            "tool_name": "stripe:create_payment_link",
        },
    )
    assert risk.status_code == 200
    assert risk.json()["needs_approval"] is True


def test_approval_request_lifecycle(client, auth_headers):
    client.post(
        "/api/accounts/sync",
        headers=auth_headers,
        json={"accounts": [{"id": "ca_google_123", "connection": "google-oauth2", "scopes": ["gmail.send"]}]},
    )
    approval = client.post(
        "/api/approvals/request",
        headers=auth_headers,
        json={
            "agent_name": "FreelanceCOOAgent",
            "provider": "google",
            "tool_name": "gmail:send_email",
            "action": "send_email",
            "input": {"draft_id": "draft-1"},
        },
    )
    assert approval.status_code == 200
    approval_payload = approval.json()
    assert approval_payload["status"] == "pending"

    status_response = client.get(
        f"/api/approvals/{approval_payload['activity_log_id']}",
        headers=auth_headers,
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] in {"approved", "pending"}


def test_failed_approval_activity_is_terminal(client, auth_headers):
    client.post(
        "/api/accounts/sync",
        headers=auth_headers,
        json={"accounts": [{"id": "ca_google_123", "connection": "google-oauth2", "scopes": ["gmail.send"]}]},
    )
    approval = client.post(
        "/api/approvals/request",
        headers=auth_headers,
        json={
            "agent_name": "FreelanceCOOAgent",
            "provider": "google",
            "tool_name": "gmail:send_email",
            "action": "send_email",
            "input": {"draft_id": "draft-2"},
        },
    )
    activity_id = approval.json()["activity_log_id"]

    update = client.patch(
        f"/api/activity/{activity_id}",
        headers=auth_headers,
        json={"status": "failed"},
    )
    assert update.status_code == 200

    status_response = client.get(
        f"/api/approvals/{activity_id}",
        headers=auth_headers,
    )
    assert status_response.status_code == 200
    payload = status_response.json()
    assert payload["status"] == "failed"
    assert payload["detail"] == "The approved action failed during execution."


def test_token_exchange_requires_subject_token_when_mock_disabled(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'strict.db'}"
    settings = Settings(
        database_url=database_url,
        cors_origins=["http://localhost:3000"],
        internal_api_shared_secret="test-secret",
        allow_mock_token_vault=False,
        allow_mock_connected_accounts=False,
        auto_approve_delay_seconds=0,
        auto_approve_when_ciba_unavailable=True,
    )
    app = create_app(settings)
    headers = {
        "x-consentos-internal-secret": "test-secret",
        "x-consentos-user-sub": "auth0|strict-user",
        "x-consentos-user-email": "strict@example.com",
    }

    with TestClient(app) as strict_client:
        sync_response = strict_client.post(
            "/api/accounts/sync",
            headers=headers,
            json={"accounts": [{"id": "ca_google_123", "connection": "google-oauth2", "scopes": ["gmail.send"]}]},
        )
        assert sync_response.status_code == 200

        token_response = strict_client.post(
            "/api/token-vault/exchange",
            headers=headers,
            json={"provider": "google"},
        )
        assert token_response.status_code == 428


def test_auth_diagnostics_reports_mock_fallbacks(client, auth_headers):
    response = client.get("/api/auth/diagnostics", headers=auth_headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["environment"] == "development"
    assert payload["mock_fallbacks_enabled"] == [
        "mock_connected_accounts",
        "mock_token_vault",
        "auto_approve_when_ciba_unavailable",
    ]


def test_health_ready_reports_ok_when_auth0_is_configured(monkeypatch, tmp_path):
    async def fake_discovery(self):
        return {"backchannel_authentication_endpoint": "https://tenant.example/bc-authorize"}, None

    monkeypatch.setattr(Auth0DiagnosticsService, "_fetch_openid_configuration", fake_discovery)

    database_url = f"sqlite:///{tmp_path / 'healthy.db'}"
    settings = Settings(
        database_url=database_url,
        cors_origins=["http://localhost:3000"],
        internal_api_shared_secret="test-secret",
        environment="production",
        auth0_domain="tenant.example",
        auth0_client_id="client-id",
        auth0_client_secret="client-secret",
        auth0_ciba_client_id="ciba-client-id",
        auth0_ciba_client_secret="ciba-client-secret",
        allow_mock_token_vault=False,
        allow_mock_connected_accounts=False,
        auto_approve_when_ciba_unavailable=False,
    )
    app = create_app(settings)

    with TestClient(app) as healthy_client:
        response = healthy_client.get("/health/ready")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert all(check["status"] == "ok" for check in payload["checks"])


def test_policy_simulation_reports_approval_required_when_live_ready(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'simulate.db'}"
    settings = Settings(
        database_url=database_url,
        cors_origins=["http://localhost:3000"],
        internal_api_shared_secret="test-secret",
        auth0_domain="tenant.example",
        auth0_client_id="client-id",
        auth0_client_secret="client-secret",
        auth0_ciba_client_id="ciba-client-id",
        auth0_ciba_client_secret="ciba-client-secret",
        allow_mock_connected_accounts=False,
        allow_mock_token_vault=False,
        auto_approve_when_ciba_unavailable=False,
    )
    app = create_app(settings)
    headers = {
        "x-consentos-internal-secret": "test-secret",
        "x-consentos-user-sub": "auth0|simulate-user",
        "x-consentos-user-email": "simulate@example.com",
    }

    with TestClient(app) as strict_client:
        strict_client.post(
            "/api/accounts/sync",
            headers=headers,
            json={"accounts": [{"id": "ca_stripe_123", "connection": "stripe", "scopes": ["payment_links.write"]}]},
        )
        response = strict_client.post(
            "/api/permissions/simulate",
            headers=headers,
            json={
                "agent_name": "FreelanceCOOAgent",
                "provider": "stripe",
                "tool_name": "stripe:create_payment_link",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["decision"] == "approval_required"
        assert payload["connected_account_status"] == "connected"
        assert payload["strict_live_mode"] is True


def test_policy_simulation_reports_policy_block(client, auth_headers):
    response = client.post(
        "/api/permissions/simulate",
        headers=auth_headers,
        json={
            "agent_name": "FreelanceCOOAgent",
            "provider": "github",
            "tool_name": "github:open_issue",
            "connected_account_present": True,
            "strict_live_required": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["decision"] == "allowed"

    client.post(
        "/api/permissions",
        headers=auth_headers,
        json={
            "agent_name": "FreelanceCOOAgent",
            "provider": "github",
            "tool_name": "github:open_issue",
            "is_allowed": False,
            "risk_level": "medium",
        },
    )
    blocked = client.post(
        "/api/permissions/simulate",
        headers=auth_headers,
        json={
            "agent_name": "FreelanceCOOAgent",
            "provider": "github",
            "tool_name": "github:open_issue",
            "connected_account_present": True,
            "strict_live_required": False,
        },
    )
    blocked_payload = blocked.json()
    assert blocked_payload["decision"] == "blocked"
    assert "tool_blocked_by_policy" in blocked_payload["reason_codes"]
