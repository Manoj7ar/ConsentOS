import path from "node:path";
import type { NextConfig } from "next";
import { fileURLToPath } from "node:url";

const frontendRoot = path.dirname(fileURLToPath(import.meta.url));

const nextConfig: NextConfig = {
  typedRoutes: true,
  outputFileTracingRoot: frontendRoot,
  eslint: {
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
