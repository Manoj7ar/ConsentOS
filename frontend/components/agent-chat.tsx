"use client";

import { FormEvent, useEffect, useState } from "react";

import { ApprovalBanner } from "@/components/approval-banner";
import { getDisplayErrorMessage } from "@/lib/error-display";
import { fetchAuthDiagnostics, fetchOrchestratorHealth, sendChat } from "@/lib/api";
import type { AuthDiagnostics, ChatMessage, OrchestratorHealth } from "@/lib/types";

const initialMessages: ChatMessage[] = [
  {
    role: "assistant",
    content:
      "I can run invoice collections, calendar follow-ups, Slack-to-GitHub escalation, and GitHub issue review when live-account checks are green."
  }
];

type AgentChatProps = {
  draftPrompt?: string;
  onDraftConsumed?: () => void;
};

export function AgentChat({ draftPrompt, onDraftConsumed }: AgentChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [pendingApprovalIds, setPendingApprovalIds] = useState<number[]>([]);
  const [diagnostics, setDiagnostics] = useState<AuthDiagnostics | null>(null);
  const [orchestratorHealth, setOrchestratorHealth] = useState<OrchestratorHealth | null>(null);
  const [readinessError, setReadinessError] = useState<string | null>(null);

  useEffect(() => {
    async function loadReadiness() {
      const [authResult, orchestratorResult] = await Promise.allSettled([
        fetchAuthDiagnostics(),
        fetchOrchestratorHealth()
      ]);
      if (authResult.status === "fulfilled") {
        setDiagnostics(authResult.value);
      }
      if (orchestratorResult.status === "fulfilled") {
        setOrchestratorHealth(orchestratorResult.value);
      }
      if (authResult.status === "rejected") {
        setReadinessError(getDisplayErrorMessage(authResult.reason));
        return;
      }
      if (orchestratorResult.status === "rejected") {
        setReadinessError(getDisplayErrorMessage(orchestratorResult.reason));
        return;
      }
      setReadinessError(null);
    }

    void loadReadiness();
  }, []);

  useEffect(() => {
    if (!draftPrompt) {
      return;
    }
    setInput(draftPrompt);
    onDraftConsumed?.();
  }, [draftPrompt, onDraftConsumed]);

  const blockingMessages = [
    ...(diagnostics?.blocking_checks.map((check) => check.detail) ?? []),
    ...((orchestratorHealth?.checks ?? []).filter((check) => check.status !== "ok").map((check) => check.detail) ?? [])
  ];
  const isExecutionBlocked = Boolean(
    readinessError ||
      !diagnostics?.strict_live_mode ||
      diagnostics?.status !== "ok" ||
      orchestratorHealth?.status !== "ok" ||
      blockingMessages.length
  );

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!input.trim() || isExecutionBlocked) {
      return;
    }

    const userMessage: ChatMessage = { role: "user", content: input.trim() };
    const nextMessages = [...messages, userMessage];
    setMessages(nextMessages);
    setInput("");
    setIsSubmitting(true);

    try {
      const response = await sendChat(nextMessages);
      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: response.assistant_message,
        metadata: response.metadata
      };
      setMessages([...nextMessages, assistantMessage]);
      const approvals = (response.metadata.pending_approval_ids as number[] | undefined) ?? [];
      if (approvals.length) {
        setPendingApprovalIds(approvals);
      }
    } catch (error) {
      setMessages([
        ...nextMessages,
        { role: "assistant", content: `Request failed: ${getDisplayErrorMessage(error)}` }
      ]);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="panel panel-chat">
      <div className="panel__header">
        <div>
          <p className="eyebrow">Freelance COO Agent</p>
          <h2>Run explicit workflows with approval gates and live-account checks</h2>
        </div>
      </div>

      {isExecutionBlocked ? (
        <div className="error-banner">
          Live execution is blocked.
          {blockingMessages.length ? ` ${blockingMessages[0]}` : ""}
        </div>
      ) : null}

      {readinessError ? <div className="error-banner">{readinessError}</div> : null}

      <div className="chat-log">
        {messages.map((message, index) => (
          <article className={`chat-bubble chat-${message.role}`} key={`${message.role}-${index}`}>
            <span className="chat-role">{message.role}</span>
            <p>{message.content}</p>
            {message.role === "assistant" && message.metadata ? (
              <div className="chat-metadata">
                {typeof message.metadata.workflow_id === "string" ? (
                  <p className="muted">
                    Workflow: {String(message.metadata.workflow_id).replaceAll("_", " ")} | Status:{" "}
                    {String(message.metadata.workflow_status ?? "unknown").replaceAll("_", " ")}
                  </p>
                ) : null}
                {Array.isArray(message.metadata.plan_steps) && message.metadata.plan_steps.length ? (
                  <ul className="chat-plan-steps">
                    {message.metadata.plan_steps.map((step, stepIndex) => (
                      <li key={`${index}-${stepIndex}`}>{String(step)}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}
          </article>
        ))}
        {isSubmitting ? <div className="chat-loading">Thinking and checking policies...</div> : null}
      </div>

      {pendingApprovalIds.length ? (
        <div className="approval-stack">
          {pendingApprovalIds.map((id) => (
            <ApprovalBanner
              key={id}
              activityId={id}
              onResolved={(resolvedId) =>
                setPendingApprovalIds((current) => current.filter((candidate) => candidate !== resolvedId))
              }
            />
          ))}
        </div>
      ) : null}

      <form className="chat-form" onSubmit={onSubmit}>
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Examples: chase overdue invoices, what is on my calendar, schedule a follow-up with client@example.com on 2026-04-01, or review GitHub issues for owner/repo."
        />
        <button className="primary-button" type="submit" disabled={isSubmitting || isExecutionBlocked}>
          Send
        </button>
      </form>
    </section>
  );
}
