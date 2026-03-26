"use client";

import { StatusPill } from "@/components/status-pill";
import type { AuthDiagnostics } from "@/lib/types";

type Auth0StatusCardProps = {
  diagnostics: AuthDiagnostics | null;
  error: string | null;
};

const CHECK_LABELS: Record<string, string> = {
  internal_api_secret: "Internal API secret",
  dev_auth_headers: "Dev auth headers",
  auth0_discovery: "Auth0 tenant",
  connected_accounts: "Connected Accounts",
  provider_connections: "Provider mappings",
  token_vault: "Token Vault",
  ciba: "CIBA approvals",
  mock_fallbacks: "Mock fallbacks"
};

export function Auth0StatusCard({ diagnostics, error }: Auth0StatusCardProps) {
  return (
    <section className="diagnostics-card">
      <div className="diagnostics-card__header">
        <div>
          <p className="eyebrow">Auth0 Status</p>
          <h3>Integration readiness and fallback state</h3>
        </div>
        <StatusPill status={diagnostics?.status ?? "unknown"} />
      </div>

      {error ? <div className="error-banner diagnostics-error">{error}</div> : null}

      {diagnostics ? (
        <>
          <p className="muted diagnostics-summary">
            Environment: {diagnostics.environment}. Strict live mode:{" "}
            {diagnostics.strict_live_mode ? "enabled" : "disabled"}.{" "}
            {diagnostics.blocking_checks.length
              ? `${diagnostics.blocking_checks.length} blocking checks still need attention.`
              : "All live-execution checks are currently clear."}
          </p>
          {diagnostics.blocking_checks.length ? (
            <div className="error-banner diagnostics-error">
              Blocking checks: {diagnostics.blocking_checks.map((check) => CHECK_LABELS[check.key] ?? check.key).join(", ")}.
            </div>
          ) : null}
          <div className="diagnostics-list">
            {diagnostics.checks.map((check) => (
              <article className="diagnostic-row" key={check.key}>
                <div>
                  <strong>{CHECK_LABELS[check.key] ?? check.key}</strong>
                  <p>{check.detail}</p>
                </div>
                <StatusPill status={check.status} />
              </article>
            ))}
          </div>
        </>
      ) : (
        <p className="muted diagnostics-summary">Auth0 diagnostics are unavailable.</p>
      )}
    </section>
  );
}
