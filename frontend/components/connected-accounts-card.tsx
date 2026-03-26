"use client";

import { StatusPill } from "@/components/status-pill";
import type { ConnectedAccount } from "@/lib/types";

type ConnectedAccountsCardProps = {
  provider: { key: string; label: string; icon: string; scopes: string[] };
  account?: ConnectedAccount;
  connectUrl: string;
  onSync: () => Promise<void>;
};

export function ConnectedAccountsCard({ provider, account, connectUrl, onSync }: ConnectedAccountsCardProps) {
  const connectionStatus = account?.connection_status ?? "not_connected";
  const connectLabel = account ? "Reconnect in Auth0" : "Connect Account";

  return (
    <div className="provider-card">
      <div className="provider-card__header">
        <div className="provider-badge">{provider.icon}</div>
        <div>
          <h3>{provider.label}</h3>
          <p>{account?.status_detail ?? "Connect this provider through Auth0 Connected Accounts."}</p>
        </div>
        <StatusPill status={connectionStatus} />
      </div>
      <div className="provider-card__body">
        {account ? (
          <>
            <div className="provider-meta">
              <p className="muted">External user: {account.external_user_id}</p>
              {account.last_synced_at ? (
                <p className="muted">Last synced: {new Date(account.last_synced_at).toLocaleString()}</p>
              ) : null}
              {account.auth0_expires_at ? (
                <p className="muted">Auth0 expiry: {new Date(account.auth0_expires_at).toLocaleString()}</p>
              ) : null}
            </div>
            {account.scopes.length ? (
              <ul className="scope-list">
                {account.scopes.map((scope) => (
                  <li key={scope}>{scope}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">No scopes were stored for the latest account record.</p>
            )}
          </>
        ) : (
          <div className="muted">
            <p>Connect this provider through Auth0 Connected Accounts to expose short-lived tools to the agent.</p>
            <p>Requested scopes: {provider.scopes.join(", ")}</p>
          </div>
        )}
      </div>
      <div className="provider-card__actions">
        <a className="secondary-button" href={connectUrl}>
          {connectLabel}
        </a>
        <button className="secondary-button" onClick={() => void onSync()}>
          Sync status
        </button>
      </div>
    </div>
  );
}
