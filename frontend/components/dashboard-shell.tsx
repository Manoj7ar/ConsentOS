"use client";

import Link from "next/link";
import { useState } from "react";
import { useUser } from "@auth0/nextjs-auth0/client";

import { AgentChat } from "@/components/agent-chat";
import { AuthorizationPanel } from "@/components/authorization-panel";
import { DemoScenariosCard } from "@/components/demo-scenarios-card";

export function DashboardShell() {
  const { user, error, isLoading } = useUser();
  const [draftPrompt, setDraftPrompt] = useState("");

  if (isLoading) {
    return <div className="centered-card">Loading session...</div>;
  }

  if (error) {
    return <div className="centered-card">Session error: {error.message}</div>;
  }

  if (!user) {
    return (
      <section className="hero-shell">
        <div className="hero-copy">
          <p className="eyebrow">ConsentOS</p>
          <h1>Safe delegated actions over real accounts, with short-lived access and approval gates.</h1>
          <p>
            Connect Google, GitHub, Stripe, and Slack through Auth0 Connected Accounts. ConsentOS keeps provider
            tokens in Token Vault, routes agent actions through per-tool policy, and forces approval before risky
            writes land in your real systems.
          </p>
          <div className="hero-actions">
            <a className="primary-button" href="/auth/login">
              Log In with Auth0
            </a>
            <Link className="secondary-button" href="/activity">
              View Activity
            </Link>
          </div>
        </div>
      </section>
    );
  }

  return (
    <>
      <DemoScenariosCard onUsePrompt={setDraftPrompt} />
      <div className="dashboard-grid">
        <AgentChat draftPrompt={draftPrompt} onDraftConsumed={() => setDraftPrompt("")} />
        <AuthorizationPanel />
      </div>
    </>
  );
}
