from __future__ import annotations

from typing import Any

import httpx

from app.config import Settings
from app.schemas.diagnostics import AuthDiagnosticsResponse, DiagnosticCheck, ReadinessResponse


class Auth0DiagnosticsService:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def collect(self) -> AuthDiagnosticsResponse:
        discovery, discovery_error = await self._fetch_openid_configuration()
        checks = [
            self._internal_secret_check(),
            self._dev_auth_headers_check(),
            self._auth0_discovery_check(discovery_error),
            self._connected_accounts_check(),
            self._provider_connections_check(),
            self._token_vault_check(),
            self._ciba_check(discovery),
            self._mock_fallbacks_check(),
        ]
        blocking_checks = [check for check in checks if check.status != "ok"]
        return AuthDiagnosticsResponse(
            status=self._overall_status(checks),
            strict_live_mode=self.settings.strict_live_mode,
            environment=self.settings.environment,
            mock_fallbacks_enabled=self._enabled_mock_fallbacks(),
            checks=checks,
            blocking_checks=blocking_checks,
        )

    async def readiness(self) -> ReadinessResponse:
        diagnostics = await self.collect()
        return ReadinessResponse(
            status=diagnostics.status,
            strict_live_mode=diagnostics.strict_live_mode,
            checks=diagnostics.checks,
            blocking_checks=diagnostics.blocking_checks,
        )

    def _internal_secret_check(self) -> DiagnosticCheck:
        if not self.settings.has_valid_internal_api_shared_secret:
            return DiagnosticCheck(
                key="internal_api_secret",
                status="error",
                code="internal_api_shared_secret_invalid",
                detail="INTERNAL_API_SHARED_SECRET must be set to a strong non-placeholder value.",
            )
        return DiagnosticCheck(
            key="internal_api_secret",
            status="ok",
            code="internal_api_shared_secret_ready",
            detail="The internal API shared secret is configured.",
        )

    def _dev_auth_headers_check(self) -> DiagnosticCheck:
        if self.settings.allow_dev_auth_headers:
            return DiagnosticCheck(
                key="dev_auth_headers",
                status="error",
                code="dev_auth_headers_enabled",
                detail="Development auth headers are enabled. Strict live mode requires them to be disabled.",
            )
        return DiagnosticCheck(
            key="dev_auth_headers",
            status="ok",
            code="dev_auth_headers_disabled",
            detail="Development auth headers are disabled.",
        )

    async def _fetch_openid_configuration(self) -> tuple[dict[str, Any] | None, str | None]:
        if not self.settings.auth0_base_url:
            return None, "BACKEND_AUTH0_DOMAIN is not configured."

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.settings.auth0_base_url}/.well-known/openid-configuration")
                response.raise_for_status()
                payload = response.json()
                if isinstance(payload, dict):
                    return payload, None
                return None, "Auth0 discovery returned an unexpected payload."
        except httpx.HTTPError as exc:
            return None, f"Unable to reach Auth0 discovery: {exc}"

    def _auth0_discovery_check(self, discovery_error: str | None) -> DiagnosticCheck:
        if discovery_error:
            return DiagnosticCheck(
                key="auth0_discovery",
                status="error",
                code="auth0_discovery_unavailable",
                detail=discovery_error,
            )
        return DiagnosticCheck(
            key="auth0_discovery",
            status="ok",
            code="auth0_discovery_ready",
            detail="Auth0 tenant discovery is reachable.",
        )

    def _connected_accounts_check(self) -> DiagnosticCheck:
        if not self.settings.auth0_my_account_audience:
            return DiagnosticCheck(
                key="connected_accounts",
                status="error",
                code="connected_accounts_audience_missing",
                detail="Connected Accounts sync needs BACKEND_AUTH0_DOMAIN so the My Account audience can be derived.",
            )
        if not self.settings.auth0_connected_accounts_scope.strip():
            return DiagnosticCheck(
                key="connected_accounts",
                status="error",
                code="connected_accounts_scope_missing",
                detail="BACKEND_AUTH0_CONNECTED_ACCOUNTS_SCOPE is empty.",
            )
        return DiagnosticCheck(
            key="connected_accounts",
            status="ok",
            code="connected_accounts_ready",
            detail=(
                f"Connected Accounts sync is configured for audience {self.settings.auth0_my_account_audience} "
                f"with scopes '{self.settings.auth0_connected_accounts_scope}'."
            ),
        )

    def _provider_connections_check(self) -> DiagnosticCheck:
        mapping = {
            "google": self.settings.google_connection_name,
            "github": self.settings.github_connection_name,
            "stripe": self.settings.stripe_connection_name,
            "slack": self.settings.slack_connection_name,
        }
        missing = [provider for provider, connection in mapping.items() if not connection.strip()]
        if missing:
            return DiagnosticCheck(
                key="provider_connections",
                status="error",
                code="provider_connection_missing",
                detail=f"Provider connection names are missing for: {', '.join(missing)}.",
            )
        return DiagnosticCheck(
            key="provider_connections",
            status="ok",
            code="provider_connections_ready",
            detail="Provider connection names are configured for Google, GitHub, Stripe, and Slack.",
        )

    def _token_vault_check(self) -> DiagnosticCheck:
        missing = [
            name
            for name, value in (
                ("BACKEND_AUTH0_DOMAIN", self.settings.auth0_domain),
                ("BACKEND_AUTH0_CLIENT_ID", self.settings.auth0_client_id),
                ("BACKEND_AUTH0_CLIENT_SECRET", self.settings.auth0_client_secret),
            )
            if not value
        ]
        if missing:
            return DiagnosticCheck(
                key="token_vault",
                status="error",
                code="token_vault_config_missing",
                detail=(
                    "Token Vault exchange cannot run until these backend Auth0 values are set: "
                    f"{', '.join(missing)}."
                ),
            )
        return DiagnosticCheck(
            key="token_vault",
            status="ok",
            code="token_vault_ready",
            detail="Backend Auth0 client credentials are present for Token Vault exchange.",
        )

    def _ciba_check(self, discovery: dict[str, Any] | None) -> DiagnosticCheck:
        missing = [
            name
            for name, value in (
                ("BACKEND_AUTH0_DOMAIN", self.settings.auth0_domain),
                ("BACKEND_AUTH0_CIBA_CLIENT_ID", self.settings.auth0_ciba_client_id),
                ("BACKEND_AUTH0_CIBA_CLIENT_SECRET", self.settings.auth0_ciba_client_secret),
            )
            if not value
        ]
        if missing:
            return DiagnosticCheck(
                key="ciba",
                status="error",
                code="ciba_config_missing",
                detail=f"Auth0 CIBA is not configured. Missing: {', '.join(missing)}.",
            )

        if not discovery or not discovery.get("backchannel_authentication_endpoint"):
            return DiagnosticCheck(
                key="ciba",
                status="error",
                code="ciba_endpoint_missing",
                detail="Auth0 discovery does not expose a backchannel authentication endpoint for CIBA.",
            )

        return DiagnosticCheck(
            key="ciba",
            status="ok",
            code="ciba_ready",
            detail="Auth0 CIBA credentials are present and the tenant exposes a backchannel authentication endpoint.",
        )

    def _mock_fallbacks_check(self) -> DiagnosticCheck:
        enabled = self._enabled_mock_fallbacks()
        if enabled:
            return DiagnosticCheck(
                key="mock_fallbacks",
                status="error",
                code="mock_fallbacks_enabled",
                detail=f"Strict live mode requires mock fallbacks to be disabled. Enabled: {', '.join(enabled)}.",
            )
        return DiagnosticCheck(
            key="mock_fallbacks",
            status="ok",
            code="mock_fallbacks_disabled",
            detail="All mock Auth0 fallbacks are disabled.",
        )

    def _enabled_mock_fallbacks(self) -> list[str]:
        fallbacks: list[str] = []
        if self.settings.allow_mock_connected_accounts:
            fallbacks.append("mock_connected_accounts")
        if self.settings.allow_mock_token_vault:
            fallbacks.append("mock_token_vault")
        if self.settings.auto_approve_when_ciba_unavailable:
            fallbacks.append("auto_approve_when_ciba_unavailable")
        return fallbacks

    @staticmethod
    def _overall_status(checks: list[DiagnosticCheck]) -> str:
        if any(check.status != "ok" for check in checks):
            return "degraded"
        return "ok"
