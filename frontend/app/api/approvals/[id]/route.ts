import { proxyToBackend } from "@/lib/auth";

export async function GET(_: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  return proxyToBackend(`/api/approvals/${id}`, { method: "GET" });
}
