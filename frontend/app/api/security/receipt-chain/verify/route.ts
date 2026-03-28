import { proxyToBackend } from "@/lib/auth";

export async function GET() {
  return proxyToBackend("/api/security/receipt-chain/verify", { method: "GET" });
}
