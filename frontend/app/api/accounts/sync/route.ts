import { NextResponse } from "next/server";

import { buildTrustedHeaders, fetchAuth0ConnectedAccounts, jsonAuthError } from "@/lib/auth";
import { getBackendProxyUrl } from "@/lib/auth0";

function jsonFromText(text: string) {
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

export async function POST() {
  try {
    const accounts = await fetchAuth0ConnectedAccounts();
    const headers = await buildTrustedHeaders();
    const response = await fetch(`${getBackendProxyUrl()}/api/accounts/sync`, {
      method: "POST",
      headers: {
        ...headers,
        "content-type": "application/json"
      },
      body: JSON.stringify({ accounts }),
      cache: "no-store"
    });
    const text = await response.text();
    return NextResponse.json(jsonFromText(text), { status: response.status });
  } catch (error) {
    return jsonAuthError(error, {
      detail: "Failed to sync connected accounts.",
      code: "upstream_unavailable",
      status: 502
    });
  }
}
