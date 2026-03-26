from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from consentos_mcp.shared.auth_context import AgentContext, default_server_context
from consentos_mcp.shared.backend_client import BackendClient
from consentos_mcp.shared.provider_http import (
    ProviderApiError,
    create_failed_activity,
    exchange_provider_access_token,
    failed_result,
    request,
    request_json,
)
from consentos_mcp.shared.settings import get_settings
from consentos_mcp.shared.tool_utils import schedule_after_approval

mcp = FastMCP("ConsentOS GitHub")

TOOLS = {
    "github:read_open_issues": {
        "provider": "github",
        "risk": "low",
        "description": "Read open GitHub issues for a repository.",
        "requires_connected_account": True,
        "approval_mode": "never",
    },
    "github:open_issue": {
        "provider": "github",
        "risk": "medium",
        "description": "Open a new GitHub issue.",
        "requires_connected_account": True,
        "approval_mode": "policy-step-up",
    },
}
RESOURCES = {
    "github://open_issues_for_repo": {"provider": "github", "description": "Open issues for a repository."},
}

_GITHUB_HEADERS = {
    "accept": "application/vnd.github+json",
    "x-github-api-version": "2022-11-28",
}


async def fetch_open_issues(context: AgentContext, repo_slug: str) -> list[dict[str, Any]]:
    settings = get_settings()
    access_token = await exchange_provider_access_token(backend=BackendClient(), context=context, provider="github")
    response = await request(
        provider="github",
        method="GET",
        url=f"{settings.github_api_base_url}/repos/{repo_slug}/issues",
        access_token=access_token,
        params={"state": "open", "per_page": 20},
        headers=_GITHUB_HEADERS,
    )
    payload = response.json()
    if not isinstance(payload, list):
        raise ProviderApiError(provider="github", detail="GitHub returned an unexpected issues payload.")

    issues: list[dict[str, Any]] = []
    for item in payload:
        if "pull_request" in item:
            continue
        issues.append(
            {
                "title": item.get("title", "(untitled issue)"),
                "number": item.get("number"),
                "state": item.get("state", "open"),
                "url": item.get("html_url"),
            }
        )
    return issues


async def open_issues_text(context: AgentContext, repo_slug: str) -> str:
    try:
        issues = await fetch_open_issues(context, repo_slug)
    except ProviderApiError as exc:
        return f"Failed to load issues for {repo_slug}: {exc.detail}"
    if not issues:
        return f"No open issues found for {repo_slug}."
    return "\n".join(f"- #{issue['number']} {issue['title']}" for issue in issues)


async def read_open_issues_action(context: AgentContext, repo_slug: str) -> dict[str, Any]:
    backend = BackendClient()
    try:
        issues = await fetch_open_issues(context, repo_slug)
    except ProviderApiError as exc:
        activity = await create_failed_activity(
            backend=backend,
            context=context,
            provider="github",
            tool_name="github:read_open_issues",
            action="read_open_issues",
            input_payload={"repo_slug": repo_slug},
            detail=exc.detail,
        )
        return failed_result(
            provider="github",
            tool_name="github:read_open_issues",
            activity_log_id=activity["id"],
            detail=exc.detail,
        )

    summary = "\n".join(f"- #{issue['number']} {issue['title']}" for issue in issues) or f"No open issues found for {repo_slug}."
    activity = await backend.create_activity(
        context,
        provider="github",
        tool_name="github:read_open_issues",
        action="read_open_issues",
        input={"repo_slug": repo_slug, "issue_count": len(issues)},
        status="completed",
    )
    return {
        "status": "completed",
        "provider": "github",
        "tool_name": "github:read_open_issues",
        "activity_log_id": activity["id"],
        "repo_slug": repo_slug,
        "summary": summary,
        "issues": issues,
    }


async def open_issue_action(context: AgentContext, repo_slug: str, title: str, body: str) -> dict[str, Any]:
    backend = BackendClient()
    risk = await backend.require_approval(context, "github", "github:open_issue")
    if not risk["permission_allowed"]:
        return {
            "status": "blocked",
            "provider": "github",
            "tool_name": "github:open_issue",
            "detail": "Issue creation is disabled.",
        }
    if risk["needs_approval"]:
        approval = await backend.request_approval(
            context,
            provider="github",
            tool_name="github:open_issue",
            action="open_issue",
            input={"repo_slug": repo_slug, "title": title, "body": body},
        )

        async def performer() -> None:
            await _create_issue(context, repo_slug, title, body)

        schedule_after_approval(
            backend=backend,
            context=context,
            activity_log_id=approval["activity_log_id"],
            performer=performer,
        )
        return {
            "status": "pending_approval",
            "provider": "github",
            "tool_name": "github:open_issue",
            "activity_log_id": approval["activity_log_id"],
            "authorization_request_id": approval["authorization_request_id"],
            "detail": approval["detail"],
            "approval_mode": approval.get("mode"),
        }

    try:
        payload = await _create_issue(context, repo_slug, title, body)
    except ProviderApiError as exc:
        activity = await create_failed_activity(
            backend=backend,
            context=context,
            provider="github",
            tool_name="github:open_issue",
            action="open_issue",
            input_payload={"repo_slug": repo_slug, "title": title, "body": body},
            detail=exc.detail,
        )
        return failed_result(
            provider="github",
            tool_name="github:open_issue",
            activity_log_id=activity["id"],
            detail=exc.detail,
        )

    activity = await backend.create_activity(
        context,
        provider="github",
        tool_name="github:open_issue",
        action="open_issue",
        input={"repo_slug": repo_slug, "title": title},
        status="completed",
    )
    return {
        "status": "completed",
        "provider": "github",
        "tool_name": "github:open_issue",
        "activity_log_id": activity["id"],
        "issue_number": payload.get("number"),
        "url": payload.get("html_url"),
    }


async def _create_issue(context: AgentContext, repo_slug: str, title: str, body: str) -> dict[str, Any]:
    settings = get_settings()
    access_token = await exchange_provider_access_token(backend=BackendClient(), context=context, provider="github")
    return await request_json(
        provider="github",
        method="POST",
        url=f"{settings.github_api_base_url}/repos/{repo_slug}/issues",
        access_token=access_token,
        json_body={"title": title, "body": body},
        headers=_GITHUB_HEADERS,
    )


@mcp.resource("github://open_issues_for_repo/{repo_slug}")
async def open_issues_for_repo(repo_slug: str) -> str:
    return await open_issues_text(default_server_context(), repo_slug)


@mcp.tool(name="github:open_issue")
async def open_issue(repo_slug: str, title: str, body: str) -> dict[str, Any]:
    """Open a GitHub issue. Risk: medium."""
    return await open_issue_action(default_server_context(), repo_slug, title, body)


@mcp.tool(name="github:read_open_issues")
async def read_open_issues(repo_slug: str) -> dict[str, Any]:
    """Read open GitHub issues. Risk: low."""
    return await read_open_issues_action(default_server_context(), repo_slug)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
