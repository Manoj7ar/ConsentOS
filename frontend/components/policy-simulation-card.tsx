"use client";

import { useMemo, useState } from "react";

import { StatusPill } from "@/components/status-pill";
import { getDisplayErrorMessage } from "@/lib/error-display";
import { simulatePolicy } from "@/lib/api";
import type { PermissionRule, PolicySimulationRequest, PolicySimulationResult } from "@/lib/types";

type PolicySimulationCardProps = {
  rules: PermissionRule[];
};

const PRESETS: Array<{
  title: string;
  description: string;
  payload: PolicySimulationRequest;
}> = [
  {
    title: "Blocked Tool",
    description: "Shows a tool denied by policy before any provider call can happen.",
    payload: {
      agent_name: "FreelanceCOOAgent",
      provider: "github",
      tool_name: "github:open_issue",
      connected_account_present: true,
      strict_live_required: false,
      permission_allowed_override: false
    }
  },
  {
    title: "Approval Required",
    description: "Shows a high-risk Stripe write being escalated for approval.",
    payload: {
      agent_name: "FreelanceCOOAgent",
      provider: "stripe",
      tool_name: "stripe:create_payment_link",
      connected_account_present: true,
      strict_live_required: true,
      approval_window_minutes_override: 30
    }
  },
  {
    title: "Missing Account",
    description: "Shows a provider action blocked because the account is disconnected.",
    payload: {
      agent_name: "FreelanceCOOAgent",
      provider: "slack",
      tool_name: "slack:post_message",
      connected_account_present: false,
      strict_live_required: false
    }
  }
];

export function PolicySimulationCard({ rules }: PolicySimulationCardProps) {
  const [selectedTool, setSelectedTool] = useState(rules[0]?.tool_name ?? "");
  const [result, setResult] = useState<PolicySimulationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);

  const selectedRule = useMemo(
    () => rules.find((rule) => rule.tool_name === selectedTool) ?? rules[0] ?? null,
    [rules, selectedTool]
  );

  async function runSimulation(payload: PolicySimulationRequest) {
    try {
      setIsRunning(true);
      setError(null);
      setResult(await simulatePolicy(payload));
    } catch (simulationError) {
      setResult(null);
      setError(getDisplayErrorMessage(simulationError));
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <section className="diagnostics-card">
      <div className="diagnostics-card__header">
        <div>
          <p className="eyebrow">Policy Simulator</p>
          <h3>Show why a request would be allowed, escalated, or blocked</h3>
        </div>
        {result ? <StatusPill status={result.decision} /> : null}
      </div>

      <div className="simulation-controls">
        <label>
          <span className="muted">Manual tool check</span>
          <select value={selectedTool} onChange={(event) => setSelectedTool(event.target.value)}>
            {rules.map((rule) => (
              <option key={rule.tool_name} value={rule.tool_name}>
                {rule.tool_name}
              </option>
            ))}
          </select>
        </label>
        <button
          className="secondary-button"
          type="button"
          disabled={!selectedRule || isRunning}
          onClick={() =>
            selectedRule
              ? void runSimulation({
                  agent_name: selectedRule.agent_name || "FreelanceCOOAgent",
                  provider: selectedRule.provider,
                  tool_name: selectedRule.tool_name,
                  approval_window_minutes_override: selectedRule.approval_window_minutes ?? null
                })
              : undefined
          }
        >
          {isRunning ? "Running..." : "Simulate"}
        </button>
      </div>

      <div className="setup-guide-links">
        {PRESETS.map((preset) => (
          <button
            key={preset.title}
            className="secondary-button"
            type="button"
            disabled={isRunning}
            onClick={() => void runSimulation(preset.payload)}
          >
            {preset.title}
          </button>
        ))}
      </div>

      {error ? <div className="error-banner diagnostics-error">{error}</div> : null}

      {result ? (
        <div className="diagnostics-list">
          <article className="diagnostic-row">
            <div>
              <strong>Decision</strong>
              <p>{result.explanation}</p>
            </div>
            <StatusPill status={result.decision} />
          </article>
          <article className="diagnostic-row">
            <div>
              <strong>Risk and account state</strong>
              <p>
                Risk: {result.risk_level}. Connected account state: {result.connected_account_status}. Strict live
                mode: {result.strict_live_mode ? "enabled" : "disabled"}.
              </p>
            </div>
          </article>
          <article className="diagnostic-row">
            <div>
              <strong>Delegated approval window</strong>
              <p>
                {result.approval_window_minutes
                  ? `When approved, this tool can execute without another prompt for ${result.approval_window_minutes} minutes.`
                  : "No delegated approval window configured; approval is required each time for risky actions."}
              </p>
            </div>
          </article>
          <article className="diagnostic-row">
            <div>
              <strong>Global write control</strong>
              <p>
                {result.writes_globally_blocked
                  ? "Emergency write block is active, so write actions are blocked regardless of tool-level policy."
                  : "Emergency write block is inactive for this decision path."}
              </p>
            </div>
          </article>
          <article className="diagnostic-row">
            <div>
              <strong>Blast radius preview</strong>
              <p>{(result.blast_radius ?? []).join(" | ") || "No blast radius metadata available."}</p>
            </div>
          </article>
          <article className="diagnostic-row">
            <div>
              <strong>Reason codes</strong>
              <p>{result.reason_codes.join(", ")}</p>
            </div>
          </article>
        </div>
      ) : (
        <p className="muted diagnostics-summary">
          Use the simulator or presets to demonstrate the policy engine without executing provider actions.
        </p>
      )}
    </section>
  );
}
