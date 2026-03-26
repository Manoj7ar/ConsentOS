import { proxyToOrchestrator } from "@/lib/auth";

export async function POST(request: Request) {
  const body = await request.text();
  return proxyToOrchestrator("/chat", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body
  });
}
