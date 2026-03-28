"use client";

import { StatusPill } from "@/components/status-pill";
import type { ReceiptIntegritySummary, ToolBlastRadius, WriteControlStatus } from "@/lib/types";

type SecurityControlsCardProps = {
  writeControl: WriteControlStatus | null;
  receiptIntegrity: ReceiptIntegritySummary | null;
  blastRadius: ToolBlastRadius[];
  error: string | null;
  onToggleWriteControl: (nextEnabled: boolean) => Promise<void>;
  onRefresh: () => void;
};

export function SecurityControlsCard({
  writeControl,
  receiptIntegrity,
  blastRadius,
  error,
  onToggleWriteControl,
  onRefresh
}: SecurityControlsCardProps) {
  const isWriteControlEnabled = Boolean(writeControl?.enabled);

  return (
    <section className="diagnostics-card">
      <div className="diagnostics-card__header">
        <div>
          <p className="eyebrow">Security Controls</p>
          <h3>Emergency write stop and tamper-evident receipt checks</h3>
        </div>
        <StatusPill status={isWriteControlEnabled ? "blocked" : "allowed"} />
      </div>

      {error ? <div className="error-banner diagnostics-error">{error}</div> : null}

      <div className="diagnostics-list">
        <article className="diagnostic-row">
          <div>
            <strong>Emergency write stop</strong>
            <p>
              {writeControl?.detail ??
                "Blocks high-impact write tools instantly so no new write execution can be initiated."}
            </p>
          </div>
          <button
            className="secondary-button"
            type="button"
            onClick={() => void onToggleWriteControl(!isWriteControlEnabled)}
          >
            {isWriteControlEnabled ? "Disable stop" : "Enable stop"}
          </button>
        </article>

        <article className="diagnostic-row">
          <div>
            <strong>Receipt chain integrity</strong>
            <p>
              {receiptIntegrity
                ? `${receiptIntegrity.checked_records} records verified. Broken records: ${receiptIntegrity.broken_record_ids.length}.`
                : "Verifies activity receipt chain to prove audit log integrity."}
            </p>
            {receiptIntegrity?.latest_receipt_hash ? (
              <p className="muted">Latest hash: {receiptIntegrity.latest_receipt_hash.slice(0, 18)}...</p>
            ) : null}
          </div>
          <div className="security-row-actions">
            {receiptIntegrity ? <StatusPill status={receiptIntegrity.status} /> : null}
            <button className="secondary-button" type="button" onClick={onRefresh}>
              Verify chain
            </button>
          </div>
        </article>

        <article className="diagnostic-row">
          <div>
            <strong>Blast radius preview</strong>
            <p className="muted">
              {blastRadius.length
                ? "Shows downstream impact before confirming high-risk workflows."
                : "Blast radius metadata unavailable."}
            </p>
            {blastRadius.slice(0, 3).map((entry) => (
              <p key={`${entry.provider}:${entry.tool_name}`}>
                <strong>{entry.tool_name}</strong>: {entry.blast_radius.join(" | ")}
              </p>
            ))}
          </div>
        </article>
      </div>
    </section>
  );
}
