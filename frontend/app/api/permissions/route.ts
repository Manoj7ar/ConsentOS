import { proxyToBackend } from "@/lib/auth";

export async function GET() {
  return proxyToBackend("/api/permissions", { method: "GET" });
}

export async function POST(request: Request) {
  const body = await request.text();
  return proxyToBackend("/api/permissions", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body
  });
}
