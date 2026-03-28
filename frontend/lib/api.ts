import type {
  ActivityItem,
  AuthDiagnostics,
  ChatMessage,
  ConnectedAccount,
  OrchestratorHealth,
  PolicySimulationRequest,
  PolicySimulationResult,
  PermissionRule,
  ReceiptIntegritySummary,
  ToolBlastRadiusResponse,
  WriteControlStatus
} from "@/lib/types";
import { KNOWN_PROVIDERS } from "@/lib/types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly code: string | null,
    readonly status: number
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseJson<T>(response: Response): Promise<T> {
  const data = await response.json();
  if (!response.ok) {
    throw new ApiError(data.detail ?? "Request failed", typeof data.code === "string" ? data.code : null, response.status);
  }
  return data as T;
}

export async function fetchAccounts(): Promise<ConnectedAccount[]> {
  return parseJson<ConnectedAccount[]>(await fetch("/api/accounts", { cache: "no-store" }));
}

export async function connectAccount(provider: string): Promise<{ account: ConnectedAccount }> {
  return parseJson<{ account: ConnectedAccount }>(
    await fetch(`/api/accounts/${provider}`, { method: "POST" })
  );
}

export async function syncAccounts() {
  return parseJson<{ items: ConnectedAccount[]; synced?: boolean; detail?: string }>(
    await fetch("/api/accounts/sync", {
      method: "POST",
      cache: "no-store"
    })
  );
}

export function buildConnectAccountUrl(provider: string) {
  const config = KNOWN_PROVIDERS.find((candidate) => candidate.key === provider);
  if (!config) {
    throw new Error(`Unknown provider: ${provider}`);
  }
  const params = new URLSearchParams({
    connection: config.connection,
    returnTo: `/?connected_provider=${provider}`
  });
  for (const scope of config.scopes) {
    params.append("scopes", scope);
  }
  return `/auth/connect?${params.toString()}`;
}

export async function fetchPermissions(): Promise<PermissionRule[]> {
  return parseJson<PermissionRule[]>(await fetch("/api/permissions", { cache: "no-store" }));
}

export async function updatePermission(payload: PermissionRule): Promise<PermissionRule> {
  return parseJson<PermissionRule>(
    await fetch("/api/permissions", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload)
    })
  );
}

export async function fetchActivity(): Promise<ActivityItem[]> {
  const payload = await parseJson<{ items: ActivityItem[] }>(await fetch("/api/activity", { cache: "no-store" }));
  return payload.items;
}

export async function fetchReceiptIntegrity(): Promise<ReceiptIntegritySummary> {
  return parseJson<ReceiptIntegritySummary>(await fetch("/api/security/receipt-chain/verify", { cache: "no-store" }));
}

export async function fetchWriteControl(): Promise<WriteControlStatus> {
  return parseJson<WriteControlStatus>(await fetch("/api/security/write-control", { cache: "no-store" }));
}

export async function updateWriteControl(enabled: boolean): Promise<WriteControlStatus> {
  return parseJson<WriteControlStatus>(
    await fetch("/api/security/write-control", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ enabled })
    })
  );
}

export async function fetchBlastRadius(): Promise<ToolBlastRadiusResponse> {
  return parseJson<ToolBlastRadiusResponse>(await fetch("/api/permissions/blast-radius", { cache: "no-store" }));
}

export async function sendChat(messages: ChatMessage[]) {
  return parseJson<{
    assistant_message: string;
    tool_events: Record<string, unknown>[];
    metadata: Record<string, unknown>;
  }>(
    await fetch("/api/chat", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ messages })
    })
  );
}

export async function fetchApproval(activityId: number) {
  return parseJson<{
    activity_log_id: number;
    status: string;
    authorization_request_id?: string | null;
    detail?: string | null;
    mode?: string | null;
  }>(await fetch(`/api/approvals/${activityId}`, { cache: "no-store" }));
}

export async function fetchAuthDiagnostics(): Promise<AuthDiagnostics> {
  return parseJson<AuthDiagnostics>(await fetch("/api/auth/diagnostics", { cache: "no-store" }));
}

export async function fetchOrchestratorHealth(): Promise<OrchestratorHealth> {
  return parseJson<OrchestratorHealth>(await fetch("/api/orchestrator/health", { cache: "no-store" }));
}

export async function simulatePolicy(payload: PolicySimulationRequest): Promise<PolicySimulationResult> {
  return parseJson<PolicySimulationResult>(
    await fetch("/api/permissions/simulate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload)
    })
  );
}
