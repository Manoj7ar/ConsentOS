import { proxyToBackend } from "@/lib/auth";

export async function GET() {
  return proxyToBackend("/api/security/write-control", { method: "GET" });
}

export async function POST(request: Request) {
  const body = await request.text();
  return proxyToBackend("/api/security/write-control", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body
  });
}
