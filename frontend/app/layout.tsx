import type { Metadata } from "next";
import Link from "next/link";
import { IBM_Plex_Mono, Space_Grotesk } from "next/font/google";
import type { ReactNode } from "react";

import "@/styles/globals.css";

const display = Space_Grotesk({ subsets: ["latin"], variable: "--font-display" });
const mono = IBM_Plex_Mono({ subsets: ["latin"], variable: "--font-mono", weight: ["400", "500"] });

export const metadata: Metadata = {
  title: "ConsentOS",
  description: "Authorization firewall for AI agents"
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${display.variable} ${mono.variable}`}>
        <div className="page-shell">
          <header className="site-header">
            <Link href="/" className="brand-mark">
              ConsentOS
            </Link>
            <nav>
              <Link href="/">Dashboard</Link>
              <Link href="/activity">Activity</Link>
              <a href="/auth/logout">Log Out</a>
            </nav>
          </header>
          <main>{children}</main>
        </div>
      </body>
    </html>
  );
}
