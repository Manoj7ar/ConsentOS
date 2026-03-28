from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models.user import User
from app.services.connected_accounts_service import ConnectedAccountsService
from app.repositories.permissions import PermissionRepository
from app.schemas.permissions import (
    PermissionRuleRead,
    PermissionUpsert,
    PolicySimulationRequest,
    PolicySimulationResponse,
    RiskCheckResponse,
)

DEFAULT_TOOL_RISK = {
    "gmail:read_inbox_summary": "low",
    "gmail:read_unpaid_clients": "low",
    "gmail:draft_followup_email": "low",
    "gmail:send_email": "high",
    "calendar:read_upcoming_meetings": "low",
    "calendar:create_meeting": "medium",
    "github:read_open_issues": "low",
    "github:open_issue": "medium",
    "stripe:read_recent_payments": "low",
    "stripe:create_payment_link": "high",
    "slack:read_recent_mentions": "low",
    "slack:post_message": "medium",
}

KNOWN_TOOLS = [
    ("google", "gmail:read_inbox_summary"),
    ("google", "gmail:read_unpaid_clients"),
    ("google", "gmail:draft_followup_email"),
    ("google", "gmail:send_email"),
    ("google", "calendar:read_upcoming_meetings"),
    ("google", "calendar:create_meeting"),
    ("github", "github:read_open_issues"),
    ("github", "github:open_issue"),
    ("stripe", "stripe:read_recent_payments"),
    ("stripe", "stripe:create_payment_link"),
    ("slack", "slack:read_recent_mentions"),
    ("slack", "slack:post_message"),
]


class PermissionsService:
    def __init__(self, session: Session, settings: Settings | None = None):
        self.repo = PermissionRepository(session)
        self.connected_accounts_service = ConnectedAccountsService(session, settings=settings)
        self.settings = settings or get_settings()

    def list_permissions(self, user_id: int, agent_name: str = "FreelanceCOOAgent") -> list[PermissionRuleRead]:
        self.repo.clear_expired_for_user(user_id)
        rows = self.repo.list_for_user(user_id)
        indexed = {(row.agent_name, row.provider, row.tool_name): row for row in rows}
        permissions: list[PermissionRuleRead] = []
        for provider, tool_name in KNOWN_TOOLS:
            row = indexed.get((agent_name, provider, tool_name))
            if row is None:
                permissions.append(
                    PermissionRuleRead(
                        agent_name=agent_name,
                        provider=provider,
                        tool_name=tool_name,
                        is_allowed=True,
                        risk_level=DEFAULT_TOOL_RISK[tool_name],
                        approval_window_minutes=None,
                    )
                )
                continue
            permissions.append(
                PermissionRuleRead(
                    id=row.id,
                    agent_name=row.agent_name,
                    provider=row.provider,
                    tool_name=row.tool_name,
                    is_allowed=row.is_allowed,
                    risk_level=row.risk_level,
                    approval_window_minutes=row.approval_window_minutes,
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
            )
        return permissions

    def upsert_permission(self, user_id: int, payload: PermissionUpsert) -> PermissionRuleRead:
        row = self.repo.upsert(
            user_id=user_id,
            agent_name=payload.agent_name,
            provider=payload.provider,
            tool_name=payload.tool_name,
            is_allowed=payload.is_allowed,
            risk_level=payload.risk_level,
            approval_window_minutes=payload.approval_window_minutes if payload.is_allowed else None,
        )
        return PermissionRuleRead(
            id=row.id,
            agent_name=row.agent_name,
            provider=row.provider,
            tool_name=row.tool_name,
            is_allowed=row.is_allowed,
            risk_level=row.risk_level,
            approval_window_minutes=row.approval_window_minutes,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def evaluate(self, user_id: int, agent_name: str, provider: str, tool_name: str) -> RiskCheckResponse:
        self.repo.clear_expired_for_user(user_id)
        write_blocked = self._writes_are_globally_blocked(user_id)
        if write_blocked and self._is_write_tool(tool_name):
            return RiskCheckResponse(
                permission_allowed=False,
                needs_approval=False,
                risk_level=DEFAULT_TOOL_RISK.get(tool_name, "medium"),
                approval_window_minutes=None,
                writes_globally_blocked=True,
            )
        row = self.repo.get_for_tool(user_id, agent_name, provider, tool_name)
        if row is None:
            is_allowed = True
            risk_level = DEFAULT_TOOL_RISK.get(tool_name, "medium")
            approval_window_minutes = None
        else:
            is_allowed = row.is_allowed
            risk_level = row.risk_level
            approval_window_minutes = row.approval_window_minutes
        needs_approval = is_allowed and (risk_level == "high" or tool_name == "stripe:create_payment_link")
        return RiskCheckResponse(
            permission_allowed=is_allowed,
            needs_approval=needs_approval,
            risk_level=risk_level,
            approval_window_minutes=approval_window_minutes,
            writes_globally_blocked=write_blocked and self._is_write_tool(tool_name),
        )

    def simulate(self, user_id: int, payload: PolicySimulationRequest) -> PolicySimulationResponse:
        risk = self.evaluate(user_id, payload.agent_name, payload.provider, payload.tool_name)
        permission_allowed = payload.permission_allowed_override if payload.permission_allowed_override is not None else risk.permission_allowed
        approval_window_minutes = (
            payload.approval_window_minutes_override
            if payload.approval_window_minutes_override is not None
            else risk.approval_window_minutes
        )
        needs_approval = permission_allowed and risk.needs_approval
        connected_account_status = self._connected_account_status(
            user_id=user_id,
            provider=payload.provider,
            override_present=payload.connected_account_present,
        )
        reason_codes: list[str] = []
        blast_radius = self._blast_radius(payload.provider, payload.tool_name)

        if payload.strict_live_required and not self.settings.strict_live_mode:
            reason_codes.append("strict_live_disabled")
        if risk.writes_globally_blocked:
            reason_codes.append("global_write_kill_switch")
        if payload.connected_account_required and connected_account_status != "connected":
            reason_codes.append(
                "provider_account_missing" if connected_account_status == "disconnected" else "provider_account_stale"
            )
        if not permission_allowed:
            reason_codes.append("tool_blocked_by_policy")

        if reason_codes:
            decision = "blocked"
        elif needs_approval:
            decision = "approval_required"
            reason_codes.append("step_up_approval_required")
            if approval_window_minutes:
                reason_codes.append(f"approval_window_{approval_window_minutes}m")
        else:
            decision = "allowed"
            reason_codes.append("policy_allows_execution")

        return PolicySimulationResponse(
            decision=decision,
            risk_level=risk.risk_level,
            permission_allowed=permission_allowed,
            needs_approval=needs_approval,
            approval_window_minutes=approval_window_minutes,
            writes_globally_blocked=risk.writes_globally_blocked,
            blast_radius=blast_radius,
            connected_account_status=connected_account_status,
            strict_live_mode=self.settings.strict_live_mode,
            reason_codes=reason_codes,
            explanation=self._explanation(
                decision,
                connected_account_status,
                reason_codes,
                risk.risk_level,
                approval_window_minutes,
            ),
        )

    def _connected_account_status(self, *, user_id: int, provider: str, override_present: bool | None) -> str:
        if override_present is not None:
            return "connected" if override_present else "disconnected"
        for account in self.connected_accounts_service.list_accounts(user_id):
            if account.provider == provider:
                return account.connection_status
        return "disconnected"

    @staticmethod
    def _explanation(
        decision: str,
        connected_account_status: str,
        reason_codes: list[str],
        risk_level: str,
        approval_window_minutes: int | None,
    ) -> str:
        if decision == "blocked":
            if "strict_live_disabled" in reason_codes:
                return "Strict live mode is not fully enabled, so this action would be blocked before execution."
            if "provider_account_missing" in reason_codes:
                return "The provider account is not connected for this user, so the action cannot run."
            if "provider_account_stale" in reason_codes:
                return "The provider account metadata is stale, so the action should not run until it is synced again."
            return "Policy currently blocks this tool for the selected user and agent."
        if decision == "approval_required":
            if approval_window_minutes:
                return (
                    f"Policy allows this tool and sets a delegated approval window of {approval_window_minutes} minutes, "
                    f"but its {risk_level} risk still requires explicit approval before execution."
                )
            return f"Policy allows this tool, but its {risk_level} risk requires explicit approval before execution."
        if approval_window_minutes:
            return (
                f"Policy and account state allow this action. If an approval is granted, it can be reused for "
                f"{approval_window_minutes} minutes."
            )
        return "Policy and account state allow this action to execute immediately."

    def _writes_are_globally_blocked(self, user_id: int) -> bool:
        user = self.repo.session.get(User, user_id)
        return bool(user and getattr(user, "emergency_write_blocked", False))

    @staticmethod
    def _is_write_tool(tool_name: str) -> bool:
        return any(
            marker in tool_name
            for marker in ("send", "create_", "open_issue", "post_message", "draft_followup_email")
        )

    @staticmethod
    def _blast_radius(provider: str, tool_name: str) -> list[str]:
        if provider == "google" and tool_name == "gmail:send_email":
            return ["Sends outbound email as user", "May reach external recipients", "Creates irreversible communication trail"]
        if provider == "google" and tool_name == "calendar:create_meeting":
            return ["Writes calendar event", "Invites attendee email(s)", "Triggers calendar notifications"]
        if provider == "stripe" and tool_name == "stripe:create_payment_link":
            return ["Creates payable Stripe URL", "Can trigger real customer payment flow", "Visible to recipient immediately"]
        if provider == "github" and tool_name == "github:open_issue":
            return ["Creates public/internal issue artifact", "Triggers repository notifications", "Persists in engineering workflow"]
        if provider == "slack" and tool_name == "slack:post_message":
            return ["Posts in team channel", "Mentions can notify teammates", "May trigger downstream incident workflows"]
        return ["Low blast radius read-only action"]

    def approval_window_minutes_for_tool(self, user_id: int, agent_name: str, provider: str, tool_name: str) -> int | None:
        self.repo.clear_expired_for_user(user_id)
        row = self.repo.get_for_tool(user_id, agent_name, provider, tool_name)
        if row is None or not row.is_allowed:
            return None
        return row.approval_window_minutes

    def blast_radius(self, user_id: int) -> dict:
        items = []
        writes_blocked = self._writes_are_globally_blocked(user_id)
        for rule in self.list_permissions(user_id):
            items.append(
                {
                    "provider": rule.provider,
                    "tool_name": rule.tool_name,
                    "risk_level": rule.risk_level,
                    "writes_globally_blocked": writes_blocked and self._is_write_tool(rule.tool_name),
                    "blast_radius": self._blast_radius(rule.provider, rule.tool_name),
                }
            )
        return {"items": items}
