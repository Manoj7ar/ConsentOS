import { proxyToBackend } from "@/lib/auth";

export async function GET() {
  return proxyToBackend("/api/permissions/blast-radius", { method: "GET" });
}
