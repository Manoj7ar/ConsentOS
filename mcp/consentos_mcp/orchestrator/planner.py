from __future__ import annotations

import json
import re
from typing import Any

import httpx

from consentos_mcp.shared.settings import MCPSettings, get_settings

WORKFLOW_IDS = {
    "invoice_collections",
    "calendar_follow_up",
    "slack_to_github_escalation",
    "github_issue_review",
    "unsupported",
}
CONFIRMATIONS = {"yes", "yes please", "go ahead", "do it", "approve", "send them", "ship it", "continue"}
EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
REPO_RE = re.compile(r"\b[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\b")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ][0-2]\d:\d{2}(?::\d{2})?(?:Z)?)?\b")
TITLE_RE = re.compile(r"(?:called|titled|title)\s+[\"']([^\"']+)[\"']", re.IGNORECASE)


def is_confirmation(message: str) -> bool:
    return message.strip().lower() in CONFIRMATIONS


def find_pending_workflow(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    for message in reversed(messages):
        metadata = message.get("metadata", {})
        pending = metadata.get("pending_workflow")
        if message.get("role") == "assistant" and isinstance(pending, dict):
            return pending
    return None


def workflow_plan_steps(workflow_id: str, params: dict[str, Any]) -> list[str]:
    if workflow_id == "invoice_collections":
        return [
            "Read overdue invoice signals from Gmail",
            "Cross-check upcoming meetings in Calendar",
            "Draft follow-up emails",
            "Create Stripe payment links",
            "Wait for approval on high-risk actions",
        ]
    if workflow_id == "calendar_follow_up":
        if params.get("mode") == "read":
            return ["Read upcoming meetings from Calendar", "Summarize schedule pressure and next meetings"]
        return [
            "Validate meeting details",
            "Create a follow-up event in Calendar",
            "Wait for approval if policy requires step-up",
        ]
    if workflow_id == "slack_to_github_escalation":
        return [
            "Read recent Slack mentions",
            "Draft an incident summary and GitHub issue",
            "Open the GitHub issue",
            "Post a Slack acknowledgement if enabled",
        ]
    if workflow_id == "github_issue_review":
        return ["Read open issues from GitHub", "Summarize backlog state and notable issues"]
    return ["Explain supported workflows"]


def workflow_missing_fields(workflow_id: str, params: dict[str, Any]) -> list[str]:
    if workflow_id == "calendar_follow_up" and params.get("mode") == "schedule":
        required = ("title", "date_or_datetime", "attendee_email")
        return [field for field in required if not params.get(field)]
    if workflow_id in {"slack_to_github_escalation", "github_issue_review"}:
        return ["repo_slug"] if not params.get("repo_slug") else []
    return []


def clarification_prompt(workflow_id: str, missing_fields: list[str]) -> str:
    if workflow_id == "calendar_follow_up":
        return (
            "I can schedule that follow-up, but I still need: "
            + ", ".join(field.replace("_", " ") for field in missing_fields)
            + "."
        )
    if workflow_id in {"slack_to_github_escalation", "github_issue_review"}:
        return "I need the GitHub repository in `owner/repo` form before I can continue."
    return "I need a bit more detail before I can continue."


def merge_params(workflow_id: str, current: dict[str, Any], message: str) -> dict[str, Any]:
    merged = dict(current)
    extracted = _fallback_params_for_workflow(workflow_id, message)
    for key, value in extracted.items():
        if value and not merged.get(key):
            merged[key] = value
    return merged


async def select_workflow(messages: list[dict[str, Any]], settings: MCPSettings | None = None) -> dict[str, Any]:
    last_user_message = next((message["content"] for message in reversed(messages) if message["role"] == "user"), "")
    active_settings = settings or get_settings()
    llm_selection = await _llm_select(last_user_message, active_settings)
    if llm_selection:
        return llm_selection
    return _fallback_select(last_user_message)


async def _llm_select(message: str, settings: MCPSettings) -> dict[str, Any] | None:
    if not settings.gemini_api_key:
        return None

    prompt = (
        "Classify the user's request into one workflow and extract any obvious parameters.\n"
        "Supported workflow_id values: invoice_collections, calendar_follow_up, slack_to_github_escalation, "
        "github_issue_review, unsupported.\n"
        "For calendar_follow_up include params.mode = read or schedule. Extract attendee_email, title, "
        "date_or_datetime, repo_slug, and slack_acknowledgement when present.\n"
        "Return strict JSON with keys workflow_id and params."
    )
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                f"{settings.gemini_api_base_url}/models/{settings.gemini_model}:generateContent",
                params={"key": settings.gemini_api_key},
                json={
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": f"{prompt}\n\nUser request:\n{message}"}],
                        }
                    ],
                    "generationConfig": {
                        "temperature": 0,
                        "responseMimeType": "application/json",
                    },
                },
            )
            response.raise_for_status()
            payload = response.json()
        content = payload["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(content)
    except Exception:
        return None

    workflow_id = parsed.get("workflow_id")
    if workflow_id not in WORKFLOW_IDS:
        return None
    params = parsed.get("params", {})
    if not isinstance(params, dict):
        params = {}
    return {"workflow_id": workflow_id, "params": _normalize_params(workflow_id, params)}


def _fallback_select(message: str) -> dict[str, Any]:
    lowered = message.lower()
    if any(token in lowered for token in ("invoice", "late payment", "overdue", "payment link", "follow up with clients")):
        return {"workflow_id": "invoice_collections", "params": {}}
    if "slack" in lowered and any(token in lowered for token in ("github", "issue", "bug", "incident", "escalat")):
        return {
            "workflow_id": "slack_to_github_escalation",
            "params": _normalize_params("slack_to_github_escalation", _fallback_params_for_workflow("slack_to_github_escalation", message)),
        }
    if "github" in lowered and any(token in lowered for token in ("open issues", "backlog", "issue review", "review issues")):
        return {
            "workflow_id": "github_issue_review",
            "params": _normalize_params("github_issue_review", _fallback_params_for_workflow("github_issue_review", message)),
        }
    if any(token in lowered for token in ("calendar", "meeting", "schedule")):
        return {
            "workflow_id": "calendar_follow_up",
            "params": _normalize_params("calendar_follow_up", _fallback_params_for_workflow("calendar_follow_up", message)),
        }
    return {"workflow_id": "unsupported", "params": {}}


def _fallback_params_for_workflow(workflow_id: str, message: str) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if workflow_id == "calendar_follow_up":
        lowered = message.lower()
        params["mode"] = "schedule" if any(token in lowered for token in ("schedule", "create", "set up")) else "read"
        params["attendee_email"] = _match_first(EMAIL_RE, message)
        params["date_or_datetime"] = _match_first(DATE_RE, message)
        title_match = TITLE_RE.search(message)
        if title_match:
            params["title"] = title_match.group(1).strip()
        elif params["mode"] == "schedule" and "follow-up" in lowered:
            params["title"] = "Follow-up meeting"
    elif workflow_id in {"slack_to_github_escalation", "github_issue_review"}:
        params["repo_slug"] = _match_first(REPO_RE, message)
        params["slack_acknowledgement"] = not any(token in message.lower() for token in ("no slack", "don't post", "without slack"))
    return params


def _normalize_params(workflow_id: str, params: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(params)
    if workflow_id == "calendar_follow_up":
        mode = str(normalized.get("mode") or "read").lower()
        normalized["mode"] = "schedule" if mode == "schedule" else "read"
    if workflow_id in {"slack_to_github_escalation", "github_issue_review"} and normalized.get("repo_slug"):
        normalized["repo_slug"] = str(normalized["repo_slug"]).strip()
    return normalized


def _match_first(pattern: re.Pattern[str], value: str) -> str | None:
    matched = pattern.search(value)
    return matched.group(0) if matched else None
