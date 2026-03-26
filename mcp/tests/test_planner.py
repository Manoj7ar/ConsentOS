from __future__ import annotations

import pytest

from consentos_mcp.orchestrator.planner import (
    find_pending_workflow,
    is_confirmation,
    merge_params,
    select_workflow,
    workflow_missing_fields,
)
from consentos_mcp.shared.settings import MCPSettings


@pytest.mark.anyio
async def test_selects_invoice_workflow_without_gemini():
    selection = await select_workflow(
        [{"role": "user", "content": "Can you chase unpaid invoices this month?"}],
        settings=MCPSettings(gemini_api_key=None),
    )
    assert selection["workflow_id"] == "invoice_collections"


@pytest.mark.anyio
async def test_selects_calendar_schedule_and_extracts_params_without_gemini():
    selection = await select_workflow(
        [
            {
                "role": "user",
                "content": "Schedule a follow-up with client@example.com on 2026-04-01 called \"Renewal review\"",
            }
        ],
        settings=MCPSettings(gemini_api_key=None),
    )
    assert selection["workflow_id"] == "calendar_follow_up"
    assert selection["params"]["mode"] == "schedule"
    assert selection["params"]["attendee_email"] == "client@example.com"
    assert selection["params"]["date_or_datetime"] == "2026-04-01"
    assert selection["params"]["title"] == "Renewal review"


def test_detects_confirmation():
    assert is_confirmation("go ahead")
    assert not is_confirmation("maybe later")


def test_find_pending_workflow():
    messages = [
        {
            "role": "assistant",
            "content": "draft",
            "metadata": {"pending_workflow": {"id": "github_issue_review", "stage": "needs_clarification"}},
        }
    ]
    assert find_pending_workflow(messages)["id"] == "github_issue_review"


def test_merge_params_fills_missing_repo_slug():
    merged = merge_params("github_issue_review", {}, "Review issues for acme/consent-firewall")
    assert merged["repo_slug"] == "acme/consent-firewall"
    assert workflow_missing_fields("github_issue_review", merged) == []
