import {
  FrontendAuthError,
  type FrontendAuthErrorCode,
  getAuth0BaseUrl,
  getAuth0Client,
  getBackendProxyUrl,
  getInternalApiSharedSecret,
  getOrchestratorBaseUrl,
  toAuthErrorPayload
} from "@/lib/auth0";
import { NextResponse } from "next/server";

function jsonFromText(text: string) {
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

type AccessTokenOptions = {
  refresh?: boolean;
  audience?: string;
  scope?: string;
};

type TrustedHeaderOptions = {
  requireSubjectToken?: boolean;
};

function authErrorResponse(
  error: unknown,
  fallback: {
    detail: string;
    code: FrontendAuthErrorCode;
    status: number;
  }
) {
  const payload = toAuthErrorPayload(error, fallback);
  return NextResponse.json(
    {
      detail: payload.detail,
      code: payload.code
    },
    { status: payload.status }
  );
}

async function getSessionOrThrow() {
  const session = await getAuth0Client().getSession();
  if (!session?.user?.sub) {
    throw new FrontendAuthError("The user does not have an active browser session.", "auth_session_missing", 401);
  }
  return session;
}

async function getAccessTokenOrThrow(
  options: AccessTokenOptions | undefined,
  failure: {
    detail: string;
    code: FrontendAuthErrorCode;
    status: number;
  }
) {
  try {
    const { token } = await getAuth0Client().getAccessToken(options);
    if (!token) {
      throw new FrontendAuthError(failure.detail, failure.code, failure.status);
    }
    return token;
  } catch (error) {
    if (error instanceof FrontendAuthError) {
      throw error;
    }
    throw new FrontendAuthError(failure.detail, failure.code, failure.status);
  }
}

export async function getSessionAccessToken() {
  await getSessionOrThrow();
  return getAccessTokenOrThrow(
    { refresh: true },
    {
      detail: "Unable to refresh the Auth0 access token for this session.",
      code: "auth_access_token_unavailable",
      status: 401
    }
  );
}

export async function getMyAccountAccessToken() {
  const baseUrl = getAuth0BaseUrl();
  await getSessionOrThrow();
  return getAccessTokenOrThrow(
    {
      refresh: true,
      audience: `${baseUrl}/me/`,
      scope: "read:me:connected_accounts"
    },
    {
      detail:
        "Unable to retrieve an Auth0 My Account token. Check connected-account scopes and session refresh settings.",
      code: "auth_my_account_token_unavailable",
      status: 403
    }
  );
}

export async function fetchAuth0ConnectedAccounts() {
  const baseUrl = getAuth0BaseUrl();
  const token = await getMyAccountAccessToken();
  const response = await fetch(`${baseUrl}/me/v1/connected-accounts`, {
    headers: {
      authorization: `Bearer ${token}`
    },
    cache: "no-store"
  });
  const text = await response.text();
  const payload = jsonFromText(text);
  if (!response.ok) {
    throw new FrontendAuthError(
      payload.detail ?? "Failed to load connected accounts from Auth0 My Account API.",
      "auth_my_account_sync_failed",
      response.status >= 400 && response.status < 600 ? response.status : 502
    );
  }
  if (Array.isArray(payload)) {
    return payload;
  }
  return Array.isArray(payload.connected_accounts) ? payload.connected_accounts : [];
}

export async function buildTrustedHeaders(options?: TrustedHeaderOptions) {
  const session = await getSessionOrThrow();
  const headers: Record<string, string> = {
    "x-consentos-internal-secret": getInternalApiSharedSecret(),
    "x-consentos-user-sub": session.user.sub
  };
  if (session.user.email) {
    headers["x-consentos-user-email"] = session.user.email;
  }

  if (options?.requireSubjectToken) {
    const subjectToken = await getSessionAccessToken();
    headers["x-consentos-auth0-subject-token"] = subjectToken;
  }

  return headers;
}

async function proxyResponse(response: Response) {
  const text = await response.text();
  return NextResponse.json(jsonFromText(text), { status: response.status });
}

async function proxyRequest(
  baseUrl: string,
  path: string,
  init: RequestInit | undefined,
  authOptions: TrustedHeaderOptions | undefined
) {
  const trustedHeaders = await buildTrustedHeaders(authOptions);
  const headers = new Headers(init?.headers);
  for (const [name, value] of Object.entries(trustedHeaders)) {
    headers.set(name, value);
  }

  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers,
    cache: "no-store"
  });
  return proxyResponse(response);
}

export async function proxyToBackend(path: string, init?: RequestInit) {
  try {
    return await proxyRequest(getBackendProxyUrl(), path, init, undefined);
  } catch (error) {
    return authErrorResponse(error, {
      detail: "Unable to reach the backend API.",
      code: "upstream_unavailable",
      status: 502
    });
  }
}

export async function proxyToOrchestrator(path: string, init?: RequestInit) {
  try {
    return await proxyRequest(getOrchestratorBaseUrl(), path, init, { requireSubjectToken: true });
  } catch (error) {
    return authErrorResponse(error, {
      detail: "Unable to reach the MCP orchestrator.",
      code: "upstream_unavailable",
      status: 502
    });
  }
}

export function jsonAuthError(
  error: unknown,
  fallback: {
    detail: string;
    code: FrontendAuthErrorCode;
    status: number;
  }
) {
  return authErrorResponse(error, fallback);
}
