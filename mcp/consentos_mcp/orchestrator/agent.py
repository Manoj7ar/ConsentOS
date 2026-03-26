from __future__ import annotations

import asyncio
from dataclasses import replace
import secrets
from typing import Any

from consentos_mcp.orchestrator.planner import (
    clarification_prompt,
    find_pending_workflow,
    is_confirmation,
    merge_params,
    select_workflow,
    workflow_missing_fields,
    workflow_plan_steps,
)
from consentos_mcp.orchestrator.tool_catalog import ToolCatalog
from consentos_mcp.shared.auth_context import AgentContext


class FreelanceCOOAgent:
    def __init__(self, catalog: ToolCatalog | None = None):
        self.catalog = catalog or ToolCatalog()

    async def respond(self, messages: list[dict[str, Any]], context: AgentContext) -> dict[str, Any]:
        last_user_message = next((message["content"] for message in reversed(messages) if message["role"] == "user"), "")
        pending_workflow = find_pending_workflow(messages)
        if pending_workflow:
            resumed = await self._resume_pending_workflow(context, pending_workflow, last_user_message)
            if resumed is not None:
                return resumed

        selection = await select_workflow(messages)
        workflow_id = selection["workflow_id"]
        params = selection.get("params", {})

        if workflow_id == "invoice_collections":
            return await self._build_invoice_plan(context)
        if workflow_id == "calendar_follow_up":
            return await self._handle_calendar_request(context, params)
        if workflow_id == "slack_to_github_escalation":
            return await self._build_slack_escalation_plan(context, params)
        if workflow_id == "github_issue_review":
            return await self._review_github_issues(context, params)
        return self._response(
            assistant_message=(
                "I support four workflows right now: invoice collections, calendar review or follow-up scheduling, "
                "Slack-to-GitHub escalation, and GitHub issue review. Ask me something in one of those lanes."
            ),
            workflow_id="unsupported",
            workflow_status="unsupported",
            plan_steps=workflow_plan_steps("unsupported", {}),
        )

    async def _resume_pending_workflow(
        self,
        context: AgentContext,
        pending_workflow: dict[str, Any],
        last_user_message: str,
    ) -> dict[str, Any] | None:
        workflow_id = str(pending_workflow.get("id", "unsupported"))
        stage = str(pending_workflow.get("stage", ""))
        params = dict(pending_workflow.get("params", {}))
        workflow_run_id = str(pending_workflow.get("workflow_run_id") or secrets.token_urlsafe(6))

        if stage == "needs_confirmation":
            if not is_confirmation(last_user_message):
                return None
            return await self._execute_workflow(
                replace(context, workflow_id=workflow_id, workflow_run_id=workflow_run_id),
                workflow_id,
                params,
            )

        if stage == "needs_clarification":
            merged_params = merge_params(workflow_id, params, last_user_message)
            missing_fields = workflow_missing_fields(workflow_id, merged_params)
            if missing_fields:
                return self._clarification_response(workflow_id, merged_params, missing_fields, workflow_run_id)
            if workflow_id == "github_issue_review" or (
                workflow_id == "calendar_follow_up" and merged_params.get("mode") == "read"
            ):
                return await self._execute_workflow(
                    replace(context, workflow_id=workflow_id, workflow_run_id=workflow_run_id),
                    workflow_id,
                    merged_params,
                )
            return await self._prepare_confirmation(context, workflow_id, merged_params, workflow_run_id)

        return None

    async def _build_invoice_plan(self, context: AgentContext) -> dict[str, Any]:
        workflow_run_id = secrets.token_urlsafe(6)
        workflow_context = replace(context, workflow_id="invoice_collections", workflow_run_id=workflow_run_id)
        unpaid_result, calendar_result = await asyncio.gather(
            self.catalog.call_tool("gmail:read_unpaid_clients", workflow_context),
            self.catalog.call_tool("calendar:read_upcoming_meetings", workflow_context),
        )
        tool_events = [unpaid_result, calendar_result]
        if unpaid_result.get("status") == "failed":
            return self._response(
                assistant_message=f"I couldn't inspect unpaid clients yet: {unpaid_result.get('detail', 'unknown Gmail error')}.",
                workflow_id="invoice_collections",
                workflow_status="failed",
                tool_events=tool_events,
                plan_steps=workflow_plan_steps("invoice_collections", {}),
            )

        clients = unpaid_result.get("clients", [])
        if not clients:
            return self._response(
                assistant_message="I didn't find any overdue clients in the configured Gmail invoice search.",
                workflow_id="invoice_collections",
                workflow_status="completed",
                tool_events=tool_events,
                plan_steps=workflow_plan_steps("invoice_collections", {}),
            )

        meetings = calendar_result.get("events", []) if calendar_result.get("status") == "completed" else []
        client_lines = ", ".join(f"{item['client_email']} ({item['amount']})" for item in clients[:5])
        meeting_lines = ", ".join(f"{meeting['title']} on {meeting['date']}" for meeting in meetings[:3]) or "none"
        message = (
            f"I found {len(clients)} overdue clients: {client_lines}. "
            f"Upcoming meetings that may affect follow-up timing: {meeting_lines}. "
            "I can draft follow-up emails and create Stripe payment links for these clients. Confirm if you want me to continue."
        )
        return self._response(
            assistant_message=message,
            workflow_id="invoice_collections",
            workflow_status="needs_confirmation",
            tool_events=tool_events,
            plan_steps=workflow_plan_steps("invoice_collections", {}),
            pending_confirmation=True,
            pending_workflow={
                "id": "invoice_collections",
                "stage": "needs_confirmation",
                "workflow_run_id": workflow_run_id,
                "params": {"clients": clients},
            },
            pending_actions=clients,
        )

    async def _handle_calendar_request(self, context: AgentContext, params: dict[str, Any]) -> dict[str, Any]:
        mode = params.get("mode", "read")
        missing_fields = workflow_missing_fields("calendar_follow_up", params)
        if missing_fields:
            return self._clarification_response("calendar_follow_up", params, missing_fields, secrets.token_urlsafe(6))
        if mode == "read":
            return await self._execute_calendar_read(
                replace(context, workflow_id="calendar_follow_up", workflow_run_id=secrets.token_urlsafe(6))
            )
        return await self._prepare_confirmation(context, "calendar_follow_up", params, secrets.token_urlsafe(6))

    async def _build_slack_escalation_plan(self, context: AgentContext, params: dict[str, Any]) -> dict[str, Any]:
        missing_fields = workflow_missing_fields("slack_to_github_escalation", params)
        if missing_fields:
            return self._clarification_response(
                "slack_to_github_escalation",
                params,
                missing_fields,
                secrets.token_urlsafe(6),
            )

        workflow_run_id = secrets.token_urlsafe(6)
        workflow_context = replace(context, workflow_id="slack_to_github_escalation", workflow_run_id=workflow_run_id)
        mentions_result = await self.catalog.call_tool("slack:read_recent_mentions", workflow_context)
        if mentions_result.get("status") == "failed":
            return self._response(
                assistant_message=f"I couldn't inspect Slack mentions yet: {mentions_result.get('detail', 'unknown Slack error')}.",
                workflow_id="slack_to_github_escalation",
                workflow_status="failed",
                tool_events=[mentions_result],
                plan_steps=workflow_plan_steps("slack_to_github_escalation", params),
            )

        mentions = mentions_result.get("mentions", [])
        if not mentions:
            return self._response(
                assistant_message="I didn't find any recent Slack mentions that match the configured incident filters.",
                workflow_id="slack_to_github_escalation",
                workflow_status="completed",
                tool_events=[mentions_result],
                plan_steps=workflow_plan_steps("slack_to_github_escalation", params),
            )

        issue_title, issue_body = self._build_issue_draft(mentions)
        primary_channel = mentions[0]["channel"]
        slack_text = f"I've drafted a GitHub issue for this incident and can post the link here once it's opened."
        message = (
            f"I found {len(mentions)} relevant Slack mentions and drafted a GitHub issue for `{params['repo_slug']}`. "
            f"Proposed issue title: {issue_title}. Confirm if you want me to open it"
            + (" and post a Slack acknowledgement." if params.get("slack_acknowledgement", True) else ".")
        )
        pending_params = {
            **params,
            "issue_title": issue_title,
            "issue_body": issue_body,
            "slack_channel": primary_channel,
            "slack_text": slack_text,
        }
        return self._response(
            assistant_message=message,
            workflow_id="slack_to_github_escalation",
            workflow_status="needs_confirmation",
            tool_events=[mentions_result],
            plan_steps=workflow_plan_steps("slack_to_github_escalation", pending_params),
            pending_confirmation=True,
            pending_workflow={
                "id": "slack_to_github_escalation",
                "stage": "needs_confirmation",
                "workflow_run_id": workflow_run_id,
                "params": pending_params,
            },
        )

    async def _review_github_issues(self, context: AgentContext, params: dict[str, Any]) -> dict[str, Any]:
        missing_fields = workflow_missing_fields("github_issue_review", params)
        if missing_fields:
            return self._clarification_response("github_issue_review", params, missing_fields, secrets.token_urlsafe(6))
        return await self._execute_workflow(
            replace(context, workflow_id="github_issue_review", workflow_run_id=secrets.token_urlsafe(6)),
            "github_issue_review",
            params,
        )

    async def _prepare_confirmation(
        self,
        context: AgentContext,
        workflow_id: str,
        params: dict[str, Any],
        workflow_run_id: str,
    ) -> dict[str, Any]:
        if workflow_id == "calendar_follow_up":
            assistant_message = (
                f"I can create the meeting '{params['title']}' for {params['attendee_email']} on "
                f"{params['date_or_datetime']}. Confirm if you want me to create it."
            )
        else:
            assistant_message = "I have a write action ready. Confirm if you want me to continue."
        return self._response(
            assistant_message=assistant_message,
            workflow_id=workflow_id,
            workflow_status="needs_confirmation",
            plan_steps=workflow_plan_steps(workflow_id, params),
            pending_confirmation=True,
            pending_workflow={
                "id": workflow_id,
                "stage": "needs_confirmation",
                "workflow_run_id": workflow_run_id,
                "params": params,
            },
        )

    def _clarification_response(
        self,
        workflow_id: str,
        params: dict[str, Any],
        missing_fields: list[str],
        workflow_run_id: str,
    ) -> dict[str, Any]:
        return self._response(
            assistant_message=clarification_prompt(workflow_id, missing_fields),
            workflow_id=workflow_id,
            workflow_status="needs_clarification",
            plan_steps=workflow_plan_steps(workflow_id, params),
            pending_workflow={
                "id": workflow_id,
                "stage": "needs_clarification",
                "workflow_run_id": workflow_run_id,
                "params": params,
                "missing_fields": missing_fields,
            },
        )

    async def _execute_workflow(self, context: AgentContext, workflow_id: str, params: dict[str, Any]) -> dict[str, Any]:
        if workflow_id == "invoice_collections":
            return await self._execute_invoice_actions(context, params)
        if workflow_id == "calendar_follow_up":
            if params.get("mode") == "read":
                return await self._execute_calendar_read(context)
            return await self._execute_calendar_write(context, params)
        if workflow_id == "slack_to_github_escalation":
            return await self._execute_slack_escalation(context, params)
        if workflow_id == "github_issue_review":
            return await self._execute_github_review(context, params)
        return self._response(
            assistant_message="That workflow is not supported yet.",
            workflow_id=workflow_id,
            workflow_status="unsupported",
            plan_steps=workflow_plan_steps("unsupported", {}),
        )

    async def _execute_invoice_actions(self, context: AgentContext, params: dict[str, Any]) -> dict[str, Any]:
        tool_events: list[dict[str, Any]] = []
        pending_approvals: list[int] = []
        clients = params.get("clients", [])

        for action in clients:
            draft = await self.catalog.call_tool(
                "gmail:draft_followup_email",
                context,
                client_email=action["client_email"],
                amount=action["amount"],
                due_date=action["due_date"],
            )
            tool_events.append(draft)

            send_result = await self.catalog.call_tool("gmail:send_email", context, draft_id=draft["draft_id"])
            tool_events.append(send_result)
            if send_result.get("status") == "pending_approval":
                pending_approvals.append(send_result["activity_log_id"])

            payment_link = await self.catalog.call_tool(
                "stripe:create_payment_link",
                context,
                client_email=action["client_email"],
                amount=action["amount"],
            )
            tool_events.append(payment_link)
            if payment_link.get("status") == "pending_approval":
                pending_approvals.append(payment_link["activity_log_id"])

        workflow_status = "pending_approval" if pending_approvals else "completed"
        message = (
            f"I drafted {len(clients)} follow-up emails and queued {len(clients)} payment links."
            if pending_approvals
            else f"I completed {len(clients)} follow-up drafts, sends, and payment-link actions."
        )
        if pending_approvals:
            message += " Approval is now pending for the high-risk steps."
        return self._response(
            assistant_message=message,
            workflow_id="invoice_collections",
            workflow_status=workflow_status,
            tool_events=tool_events,
            plan_steps=workflow_plan_steps("invoice_collections", params),
            pending_approval_ids=pending_approvals,
        )

    async def _execute_calendar_read(self, context: AgentContext) -> dict[str, Any]:
        result = await self.catalog.call_tool("calendar:read_upcoming_meetings", context)
        if result.get("status") == "failed":
            return self._response(
                assistant_message=f"I couldn't inspect Calendar yet: {result.get('detail', 'unknown Calendar error')}.",
                workflow_id="calendar_follow_up",
                workflow_status="failed",
                tool_events=[result],
                plan_steps=workflow_plan_steps("calendar_follow_up", {"mode": "read"}),
            )

        events = result.get("events", [])
        if not events:
            assistant_message = "Your configured calendar lookahead window is clear."
        else:
            preview = ", ".join(f"{event['title']} on {event['date']}" for event in events[:5])
            assistant_message = f"Here are the next calendar commitments I found: {preview}."
        return self._response(
            assistant_message=assistant_message,
            workflow_id="calendar_follow_up",
            workflow_status="completed",
            tool_events=[result],
            plan_steps=workflow_plan_steps("calendar_follow_up", {"mode": "read"}),
        )

    async def _execute_calendar_write(self, context: AgentContext, params: dict[str, Any]) -> dict[str, Any]:
        result = await self.catalog.call_tool(
            "calendar:create_meeting",
            context,
            title=params["title"],
            date=params["date_or_datetime"],
            attendee_email=params["attendee_email"],
        )
        pending_approvals = [result["activity_log_id"]] if result.get("status") == "pending_approval" else []
        status = "pending_approval" if pending_approvals else result.get("status", "completed")
        message = (
            f"I queued the meeting '{params['title']}' for {params['attendee_email']} on {params['date_or_datetime']}."
        )
        if pending_approvals:
            message += " Approval is pending before Calendar will create it."
        return self._response(
            assistant_message=message,
            workflow_id="calendar_follow_up",
            workflow_status=status,
            tool_events=[result],
            plan_steps=workflow_plan_steps("calendar_follow_up", params),
            pending_approval_ids=pending_approvals,
        )

    async def _execute_slack_escalation(self, context: AgentContext, params: dict[str, Any]) -> dict[str, Any]:
        tool_events: list[dict[str, Any]] = []
        pending_approvals: list[int] = []

        issue_result = await self.catalog.call_tool(
            "github:open_issue",
            context,
            repo_slug=params["repo_slug"],
            title=params["issue_title"],
            body=params["issue_body"],
        )
        tool_events.append(issue_result)
        if issue_result.get("status") == "pending_approval":
            pending_approvals.append(issue_result["activity_log_id"])

        if params.get("slack_acknowledgement", True):
            slack_result = await self.catalog.call_tool(
                "slack:post_message",
                context,
                channel=params["slack_channel"],
                text=params["slack_text"],
            )
            tool_events.append(slack_result)
            if slack_result.get("status") == "pending_approval":
                pending_approvals.append(slack_result["activity_log_id"])

        message = f"I queued the GitHub incident escalation for `{params['repo_slug']}`."
        if pending_approvals:
            message += " Approval is pending for one or more write actions."
        else:
            message += " The write actions completed without additional approval."
        return self._response(
            assistant_message=message,
            workflow_id="slack_to_github_escalation",
            workflow_status="pending_approval" if pending_approvals else "completed",
            tool_events=tool_events,
            plan_steps=workflow_plan_steps("slack_to_github_escalation", params),
            pending_approval_ids=pending_approvals,
        )

    async def _execute_github_review(self, context: AgentContext, params: dict[str, Any]) -> dict[str, Any]:
        result = await self.catalog.call_tool("github:read_open_issues", context, repo_slug=params["repo_slug"])
        if result.get("status") == "failed":
            return self._response(
                assistant_message=f"I couldn't inspect `{params['repo_slug']}` yet: {result.get('detail', 'unknown GitHub error')}.",
                workflow_id="github_issue_review",
                workflow_status="failed",
                tool_events=[result],
                plan_steps=workflow_plan_steps("github_issue_review", params),
            )

        issues = result.get("issues", [])
        if not issues:
            assistant_message = f"`{params['repo_slug']}` has no open issues right now."
        else:
            preview = ", ".join(f"#{issue['number']} {issue['title']}" for issue in issues[:5])
            assistant_message = f"`{params['repo_slug']}` currently has {len(issues)} open issues. Top items: {preview}."
        return self._response(
            assistant_message=assistant_message,
            workflow_id="github_issue_review",
            workflow_status="completed",
            tool_events=[result],
            plan_steps=workflow_plan_steps("github_issue_review", params),
        )

    @staticmethod
    def _build_issue_draft(mentions: list[dict[str, Any]]) -> tuple[str, str]:
        first = mentions[0]
        title = f"Investigate Slack-reported issue from {first.get('channel', 'Slack')}"
        body_lines = ["Summary of recent Slack mentions requiring review:"]
        for mention in mentions[:5]:
            body_lines.append(f"- {mention['channel']} | {mention['user']}: {mention['text']}")
        return title, "\n".join(body_lines)

    @staticmethod
    def _response(
        *,
        assistant_message: str,
        workflow_id: str,
        workflow_status: str,
        tool_events: list[dict[str, Any]] | None = None,
        plan_steps: list[str] | None = None,
        pending_confirmation: bool = False,
        pending_workflow: dict[str, Any] | None = None,
        pending_approval_ids: list[int] | None = None,
        pending_actions: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "workflow_id": workflow_id,
            "workflow_status": workflow_status,
            "plan_steps": plan_steps or [],
            "pending_confirmation": pending_confirmation,
        }
        if pending_workflow:
            metadata["pending_workflow"] = pending_workflow
        if pending_approval_ids:
            metadata["pending_approval_ids"] = pending_approval_ids
        if pending_actions:
            metadata["pending_actions"] = pending_actions
        return {
            "assistant_message": assistant_message,
            "tool_events": tool_events or [],
            "metadata": metadata,
        }
