import { proxyToBackend } from "@/lib/auth";

export async function GET() {
  return proxyToBackend("/api/auth/diagnostics", { method: "GET" });
}
