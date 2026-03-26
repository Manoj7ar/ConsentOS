import { proxyToOrchestrator } from "@/lib/auth";

export async function GET() {
  return proxyToOrchestrator("/health/ready");
}
