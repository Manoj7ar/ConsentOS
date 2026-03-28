export type ConnectedAccount = {
  id: number;
  provider: string;
  external_user_id: string;
  scopes: string[];
  is_connected: boolean;
  connection_status: string;
  status_detail?: string | null;
  last_synced_at?: string | null;
  auth0_created_at?: string | null;
  auth0_expires_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type PermissionRule = {
  id?: number | null;
  agent_name: string;
  provider: string;
  tool_name: string;
  is_allowed: boolean;
  risk_level: string;
  approval_window_minutes?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ActivityItem = {
  id: number;
  agent_name: string;
  provider: string;
  tool_name: string;
  action: string;
  input: Record<string, unknown>;
  activity_meta: ActivityMeta;
  status: string;
  authorization_request_id?: string | null;
  created_at: string;
  receipt_id?: string | null;
  receipt_hash?: string | null;
  receipt_prev_hash?: string | null;
  chain_valid?: boolean | null;
  request_id?: string | null;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  metadata?: Record<string, unknown>;
};

export type DiagnosticCheck = {
  key: string;
  status: string;
  code: string;
  detail: string;
};

export type AuthDiagnostics = {
  status: string;
  strict_live_mode: boolean;
  environment: string;
  mock_fallbacks_enabled: string[];
  checks: DiagnosticCheck[];
  blocking_checks: DiagnosticCheck[];
};

export type OrchestratorHealth = {
  status: string;
  checks: DiagnosticCheck[];
};

export type ActivityMeta = {
  workflow_id?: string | null;
  workflow_run_id?: string | null;
  policy_decision?: string | null;
  approval_mode?: string | null;
  receipt_hash?: string | null;
  receipt_prev_hash?: string | null;
  request_id?: string | null;
};

export type PolicySimulationRequest = {
  agent_name: string;
  provider: string;
  tool_name: string;
  connected_account_required?: boolean;
  connected_account_present?: boolean | null;
  strict_live_required?: boolean;
  permission_allowed_override?: boolean | null;
  approval_window_minutes_override?: number | null;
};

export type PolicySimulationResult = {
  decision: string;
  risk_level: string;
  permission_allowed: boolean;
  needs_approval: boolean;
  approval_window_minutes?: number | null;
  writes_globally_blocked?: boolean;
  blast_radius?: string[];
  connected_account_status: string;
  strict_live_mode: boolean;
  reason_codes: string[];
  explanation: string;
};

export type WriteControlStatus = {
  enabled: boolean;
  detail: string;
};

export type ReceiptIntegritySummary = {
  status: string;
  checked_records: number;
  broken_record_ids: number[];
  latest_receipt_hash?: string | null;
  detail: string;
};

export type ToolBlastRadius = {
  provider: string;
  tool_name: string;
  risk_level: string;
  writes_globally_blocked: boolean;
  blast_radius: string[];
};

export type ToolBlastRadiusResponse = {
  items: ToolBlastRadius[];
};

export const KNOWN_PROVIDERS = [
  {
    key: "google",
    label: "Google",
    icon: "G",
    connection: "google-oauth2",
    scopes: ["gmail.readonly", "gmail.send", "calendar.readonly", "calendar.events"]
  },
  {
    key: "github",
    label: "GitHub",
    icon: "GH",
    connection: "github",
    scopes: ["repo", "read:user"]
  },
  {
    key: "stripe",
    label: "Stripe",
    icon: "S",
    connection: "stripe",
    scopes: ["customers.read", "payment_links.write", "payments.read"]
  },
  {
    key: "slack",
    label: "Slack",
    icon: "SL",
    connection: "slack",
    scopes: ["channels:history", "chat:write", "users:read"]
  }
];
