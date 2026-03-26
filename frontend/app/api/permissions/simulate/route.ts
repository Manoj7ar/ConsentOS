import { proxyToBackend } from "@/lib/auth";

export async function POST(request: Request) {
  const body = await request.text();
  return proxyToBackend("/api/permissions/simulate", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body
  });
}
