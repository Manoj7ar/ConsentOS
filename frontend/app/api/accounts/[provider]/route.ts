import { NextResponse } from "next/server";

import { buildConnectAccountUrl } from "@/lib/api";

async function redirectToConnect(request: Request, provider: string) {
  const location = buildConnectAccountUrl(provider);
  return NextResponse.redirect(new URL(location, request.url));
}

export async function GET(request: Request, context: { params: Promise<{ provider: string }> }) {
  const { provider } = await context.params;
  return redirectToConnect(request, provider);
}

export async function POST(request: Request, context: { params: Promise<{ provider: string }> }) {
  const { provider } = await context.params;
  return redirectToConnect(request, provider);
}
