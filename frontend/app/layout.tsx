import type { Metadata } from "next";
import Link from "next/link";
import { DM_Sans, Geist_Mono } from "next/font/google";
import type { ReactNode } from "react";

import "@/styles/globals.css";

const display = DM_Sans({ subsets: ["latin"], variable: "--font-display", weight: ["400", "500", "700"] });
const mono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono" });

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
