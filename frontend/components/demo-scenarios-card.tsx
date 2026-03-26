"use client";

const DEMO_SCENARIOS = [
  {
    title: "Invoice Collections",
    description: "Show a real cross-tool workflow that reads Gmail and Calendar, then proposes Stripe and email actions.",
    expected: "Confirmation and approval-required writes",
    prompt: "Chase overdue invoices this month and help me follow up with clients."
  },
  {
    title: "Calendar Review",
    description: "Show a read-only workflow that proves the assistant can inspect live account data safely.",
    expected: "Read-only summary",
    prompt: "What is on my calendar over the next week?"
  },
  {
    title: "Schedule Follow-Up",
    description: "Show a write workflow with explicit meeting details and a step-up approval path if needed.",
    expected: "Confirmation, then calendar write",
    prompt: 'Schedule a follow-up with client@example.com on 2026-04-01 called "Renewal review".'
  },
  {
    title: "Slack To GitHub",
    description: "Show escalation from recent Slack mentions into a proposed GitHub issue.",
    expected: "Confirmation and optional Slack acknowledgement",
    prompt: "Review Slack mentions and open a GitHub issue for acme/consent-firewall if there is an incident."
  },
  {
    title: "Guardrail Demo",
    description: "Use this after turning off a tool or disconnecting a provider to show the system refusing execution.",
    expected: "Blocked by policy or account state",
    prompt: "Create a payment link for a late-paying client."
  }
];

type DemoScenariosCardProps = {
  onUsePrompt: (prompt: string) => void;
};

export function DemoScenariosCard({ onUsePrompt }: DemoScenariosCardProps) {
  return (
    <section className="panel">
      <div className="panel__header">
        <div>
          <p className="eyebrow">Judge Mode</p>
          <h2>Run the strongest demo sequence without thinking</h2>
        </div>
      </div>

      <div className="setup-guide-list">
        {DEMO_SCENARIOS.map((scenario) => (
          <article className="setup-guide-item" key={scenario.title}>
            <div className="setup-guide-item__body">
              <strong>{scenario.title}</strong>
              <p>{scenario.description}</p>
              <p className="muted">Expected outcome: {scenario.expected}</p>
            </div>
            <div className="provider-card__actions">
              <button className="secondary-button" type="button" onClick={() => onUsePrompt(scenario.prompt)}>
                Use Prompt
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
