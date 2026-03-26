import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

import { getAuth0Client, toAuthErrorPayload } from "@/lib/auth0";

export async function middleware(request: NextRequest) {
  try {
    return await getAuth0Client().middleware(request);
  } catch (error) {
    const payload = toAuthErrorPayload(error, {
      detail: "Frontend authentication is not configured correctly.",
      code: "auth0_config_missing",
      status: 503
    });

    if (request.nextUrl.pathname.startsWith("/api/")) {
      return NextResponse.json(
        {
          detail: payload.detail,
          code: payload.code
        },
        { status: payload.status }
      );
    }

    return new NextResponse(payload.detail, { status: payload.status });
  }
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|sitemap.xml|robots.txt).*)"]
};
