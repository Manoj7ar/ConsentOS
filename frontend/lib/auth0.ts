import { Auth0Client } from "@auth0/nextjs-auth0/server";

export type FrontendAuthErrorCode =
  | "auth0_config_missing"
  | "auth_session_missing"
  | "auth_access_token_unavailable"
  | "auth_my_account_token_unavailable"
  | "auth_my_account_sync_failed"
  | "upstream_unavailable";

export class FrontendAuthError extends Error {
  constructor(
    message: string,
    readonly code: FrontendAuthErrorCode,
    readonly status: number
  ) {
    super(message);
    this.name = "FrontendAuthError";
  }
}

type FrontendAuthConfig = {
  auth0Domain: string;
  auth0ClientId: string;
  auth0ClientSecret: string;
  auth0Secret: string;
  auth0Audience?: string;
  auth0Scope?: string;
  appBaseUrl?: string;
  backendProxyUrl: string;
  orchestratorBaseUrl: string;
  internalApiSharedSecret: string;
};

let auth0Client: Auth0Client | null = null;
let frontendConfig: FrontendAuthConfig | null = null;

export function getAuth0Client() {
  if (auth0Client) {
    return auth0Client;
  }

  const config = getFrontendAuthConfig();
  const options: ConstructorParameters<typeof Auth0Client>[0] = {
    domain: config.auth0Domain,
    clientId: config.auth0ClientId,
    clientSecret: config.auth0ClientSecret,
    secret: config.auth0Secret
  };

  if (config.appBaseUrl) {
    options.appBaseUrl = config.appBaseUrl;
  }
  if (config.auth0Audience || config.auth0Scope) {
    options.authorizationParameters = {
      ...(config.auth0Audience ? { audience: config.auth0Audience } : {}),
      ...(config.auth0Scope ? { scope: config.auth0Scope } : {})
    };
  }

  auth0Client = new Auth0Client(options);
  return auth0Client;
}

export function getFrontendAuthConfig(): FrontendAuthConfig {
  if (frontendConfig) {
    return frontendConfig;
  }

  const missing = requiredEnvNames().filter((name) => !process.env[name]?.trim());
  if (missing.length) {
    throw new FrontendAuthError(
      `Missing required frontend Auth0 environment variables: ${missing.join(", ")}.`,
      "auth0_config_missing",
      503
    );
  }

  frontendConfig = {
    auth0Domain: normalizeDomain(process.env.AUTH0_DOMAIN!),
    auth0ClientId: process.env.AUTH0_CLIENT_ID!,
    auth0ClientSecret: process.env.AUTH0_CLIENT_SECRET!,
    auth0Secret: process.env.AUTH0_SECRET!,
    auth0Audience: process.env.AUTH0_AUDIENCE,
    auth0Scope: process.env.AUTH0_SCOPE,
    appBaseUrl: process.env.APP_BASE_URL,
    backendProxyUrl: process.env.BACKEND_PROXY_URL ?? "http://localhost:8000",
    orchestratorBaseUrl: process.env.ORCHESTRATOR_BASE_URL ?? "http://localhost:8100",
    internalApiSharedSecret: process.env.INTERNAL_API_SHARED_SECRET ?? "change-me"
  };
  return frontendConfig;
}

export function getAuth0BaseUrl() {
  return `https://${getFrontendAuthConfig().auth0Domain}`;
}

export function getBackendProxyUrl() {
  return getFrontendAuthConfig().backendProxyUrl;
}

export function getOrchestratorBaseUrl() {
  return getFrontendAuthConfig().orchestratorBaseUrl;
}

export function getInternalApiSharedSecret() {
  return getFrontendAuthConfig().internalApiSharedSecret;
}

export function toAuthErrorPayload(
  error: unknown,
  fallback: {
    detail: string;
    code: FrontendAuthErrorCode;
    status: number;
  }
) {
  if (error instanceof FrontendAuthError) {
    return {
      detail: error.message,
      code: error.code,
      status: error.status
    };
  }

  if (error instanceof Error) {
    return {
      detail: error.message,
      code: fallback.code,
      status: fallback.status
    };
  }

  return {
    detail: fallback.detail,
    code: fallback.code,
    status: fallback.status
  };
}

function requiredEnvNames() {
  return ["AUTH0_DOMAIN", "AUTH0_CLIENT_ID", "AUTH0_CLIENT_SECRET", "AUTH0_SECRET"] as const;
}

function normalizeDomain(domain: string) {
  return domain.replace(/^https?:\/\//, "").replace(/\/+$/, "");
}
