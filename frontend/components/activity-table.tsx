"use client";

import { Fragment, useEffect, useState } from "react";

import { StatusPill } from "@/components/status-pill";
import { getDisplayErrorMessage } from "@/lib/error-display";
import { fetchActivity } from "@/lib/api";
import type { ActivityItem } from "@/lib/types";

export function ActivityTable() {
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  async function load() {
    try {
      setItems(await fetchActivity());
      setError(null);
    } catch (loadError) {
      setError(getDisplayErrorMessage(loadError));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <p className="eyebrow">Activity Timeline</p>
          <h2>Every agent action is logged with provider and status</h2>
        </div>
        <button className="secondary-button" onClick={() => void load()}>
          Refresh
        </button>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}

      <div className="table-shell">
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Workflow</th>
              <th>Agent</th>
              <th>Tool</th>
              <th>Decision</th>
              <th>Status</th>
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const cleanInput = Object.fromEntries(
                Object.entries(item.input).filter(([key]) => key !== "_consentos")
              );
              const inputSummary = Object.entries(cleanInput)
                .slice(0, 3)
                .map(([key, value]) => `${key}: ${String(value)}`)
                .join(" | ");
              const isExpanded = expandedId === item.id;
              return (
                <Fragment key={item.id}>
                  <tr>
                    <td>{new Date(item.created_at).toLocaleString()}</td>
                    <td>{item.activity_meta.workflow_id?.replaceAll("_", " ") ?? "ad hoc"}</td>
                    <td>{item.agent_name}</td>
                    <td>
                      {item.provider} / {item.tool_name}
                    </td>
                    <td>{item.activity_meta.policy_decision ?? "executed"}</td>
                    <td>
                      <StatusPill status={item.status} />
                    </td>
                    <td>
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => setExpandedId((current) => (current === item.id ? null : item.id))}
                      >
                        {isExpanded ? "Hide" : "Show"}
                      </button>
                    </td>
                  </tr>
                  {isExpanded ? (
                    <tr className="activity-detail-row">
                      <td colSpan={7}>
                        <div className="activity-detail">
                          <p>
                            <strong>Action:</strong> {item.action}
                          </p>
                          <p>
                            <strong>Workflow run:</strong> {item.activity_meta.workflow_run_id ?? "n/a"}
                          </p>
                          <p>
                            <strong>Approval mode:</strong> {item.activity_meta.approval_mode ?? "n/a"}
                          </p>
                          <p>
                            <strong>Authorization request:</strong> {item.authorization_request_id ?? "none"}
                          </p>
                          <p>
                            <strong>Input summary:</strong> {inputSummary || "No additional input payload."}
                          </p>
                          <p>
                            <strong>Receipt hash:</strong> {item.receipt_hash ?? item.activity_meta.receipt_hash ?? "n/a"}
                          </p>
                          <p>
                            <strong>Previous hash:</strong> {item.receipt_prev_hash ?? item.activity_meta.receipt_prev_hash ?? "n/a"}
                          </p>
                          <p>
                            <strong>Request ID:</strong> {item.request_id ?? item.activity_meta.request_id ?? "n/a"}
                          </p>
                        </div>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
            {!items.length ? (
              <tr>
                <td colSpan={7} className="empty-cell">
                  No activity yet. Run a guided demo scenario or ask the agent to inspect unpaid invoices.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}
