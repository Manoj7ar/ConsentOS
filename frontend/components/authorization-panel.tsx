"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { Auth0StatusCard } from "@/components/auth0-status-card";
import { ConnectedAccountsCard } from "@/components/connected-accounts-card";
import { PermissionToggleList } from "@/components/permission-toggle-list";
import { PolicySimulationCard } from "@/components/policy-simulation-card";
import { SetupGuideCard } from "@/components/setup-guide-card";
import { getDisplayErrorMessage } from "@/lib/error-display";
import {
  buildConnectAccountUrl,
  fetchBlastRadius,
  fetchAccounts,
  fetchAuthDiagnostics,
  fetchPermissions,
  fetchReceiptIntegrity,
  fetchWriteControl,
  syncAccounts,
  updateWriteControl,
  updatePermission
} from "@/lib/api";
import { SecurityControlsCard } from "@/components/security-controls-card";
import type {
  AuthDiagnostics,
  ConnectedAccount,
  PermissionRule,
  ReceiptIntegritySummary,
  ToolBlastRadius,
  WriteControlStatus
} from "@/lib/types";
import { KNOWN_PROVIDERS } from "@/lib/types";

export function AuthorizationPanel() {
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const [accounts, setAccounts] = useState<ConnectedAccount[]>([]);
  const [permissions, setPermissions] = useState<PermissionRule[]>([]);
  const [diagnostics, setDiagnostics] = useState<AuthDiagnostics | null>(null);
  const [writeControl, setWriteControl] = useState<WriteControlStatus | null>(null);
  const [receiptIntegrity, setReceiptIntegrity] = useState<ReceiptIntegritySummary | null>(null);
  const [blastRadius, setBlastRadius] = useState<ToolBlastRadius[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [diagnosticsError, setDiagnosticsError] = useState<string | null>(null);
  const [securityError, setSecurityError] = useState<string | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);

  async function load(options?: { sync?: boolean }) {
    const shouldSync = options?.sync ?? true;
    let nextError: string | null = null;

    if (shouldSync) {
      try {
        setIsSyncing(true);
        await syncAccounts();
      } catch (syncError) {
        nextError = getDisplayErrorMessage(syncError);
      }
    }

    const [accountsResult, permissionsResult, diagnosticsResult, writeControlResult, receiptIntegrityResult, blastRadiusResult] =
      await Promise.allSettled([
        fetchAccounts(),
        fetchPermissions(),
        fetchAuthDiagnostics(),
        fetchWriteControl(),
        fetchReceiptIntegrity(),
        fetchBlastRadius()
      ]);

    if (accountsResult.status === "fulfilled") {
      setAccounts(accountsResult.value);
    } else if (!nextError) {
      nextError = getDisplayErrorMessage(accountsResult.reason);
    }

    if (permissionsResult.status === "fulfilled") {
      setPermissions(permissionsResult.value);
    } else if (!nextError) {
      nextError = getDisplayErrorMessage(permissionsResult.reason);
    }

    if (diagnosticsResult.status === "fulfilled") {
      setDiagnostics(diagnosticsResult.value);
      setDiagnosticsError(null);
    } else {
      setDiagnostics(null);
      setDiagnosticsError(getDisplayErrorMessage(diagnosticsResult.reason));
    }

    let nextSecurityError: string | null = null;
    if (writeControlResult.status === "fulfilled") {
      setWriteControl(writeControlResult.value);
    } else {
      nextSecurityError = getDisplayErrorMessage(writeControlResult.reason);
      setWriteControl(null);
    }
    if (receiptIntegrityResult.status === "fulfilled") {
      setReceiptIntegrity(receiptIntegrityResult.value);
    } else {
      if (!nextSecurityError) {
        nextSecurityError = getDisplayErrorMessage(receiptIntegrityResult.reason);
      }
      setReceiptIntegrity(null);
    }
    if (blastRadiusResult.status === "fulfilled") {
      setBlastRadius(blastRadiusResult.value.items);
    } else {
      if (!nextSecurityError) {
        nextSecurityError = getDisplayErrorMessage(blastRadiusResult.reason);
      }
      setBlastRadius([]);
    }
    setSecurityError(nextSecurityError);

    setError(nextError);
    setIsSyncing(false);
  }

  useEffect(() => {
    void load({ sync: true });
  }, [searchKey]);

  async function onSync() {
    await load({ sync: true });
  }

  async function onToggle(rule: PermissionRule) {
    await updatePermission({
      ...rule,
      agent_name: rule.agent_name || "FreelanceCOOAgent"
    });
    await load({ sync: false });
  }

  async function onWriteControlToggle(nextEnabled: boolean) {
    await updateWriteControl(nextEnabled);
    await load({ sync: false });
  }

  return (
    <section className="panel panel-authz">
      <div className="panel__header">
        <div>
          <p className="eyebrow">Authorization Panel</p>
          <h2>Connected accounts and per-tool agent policy</h2>
        </div>
        <button className="secondary-button" onClick={() => void onSync()} disabled={isSyncing}>
          {isSyncing ? "Syncing..." : "Sync from Auth0"}
        </button>
      </div>

      {error ? <div className="error-banner">{error}</div> : null}

      <Auth0StatusCard diagnostics={diagnostics} error={diagnosticsError} />
      <SecurityControlsCard
        writeControl={writeControl}
        receiptIntegrity={receiptIntegrity}
        blastRadius={blastRadius}
        error={securityError}
        onToggleWriteControl={onWriteControlToggle}
        onRefresh={() => void load({ sync: false })}
      />
      <PolicySimulationCard rules={permissions} />
      <SetupGuideCard />

      <div className="provider-grid">
        {KNOWN_PROVIDERS.map((provider) => (
          <ConnectedAccountsCard
            key={provider.key}
            provider={provider}
            account={accounts.find((account) => account.provider === provider.key)}
            connectUrl={buildConnectAccountUrl(provider.key)}
            onSync={onSync}
          />
        ))}
      </div>

      <div className="permissions-section">
        <div className="permissions-title">
          <h3>FreelanceCOOAgent permissions</h3>
          <p className="muted">
            Toggle tools off to hard-block them, then optionally set a one-time approval window for high-risk actions.
          </p>
        </div>
        <PermissionToggleList rules={permissions} onToggle={onToggle} />
      </div>
    </section>
  );
}
