# ConsentOS 3-Minute Judge Demo Script

Use this exact flow for the required public demo video.

## 0:00 - 0:20 Intro and premise

- "ConsentOS is a policy and approval layer for agent actions on real user accounts."
- "Provider tokens stay in Auth0 Token Vault. The agent only gets short-lived access at execution time."
- "High-risk actions are escalated for explicit approval."

## 0:20 - 0:45 Readiness and security posture

- Open the dashboard and show **Auth0 Status**.
- Highlight:
  - strict live mode
  - token vault check
  - CIBA check
  - no mock fallback
- Mention that blocked checks prevent live execution.

## 0:45 - 1:25 Read-only workflow

- In Judge Mode, run **Calendar Review** prompt.
- Show that the system can read data safely without write actions.
- Point out activity entries and policy metadata.

## 1:25 - 2:20 High-risk write with approval

- Run **Invoice Collections** or **Schedule Follow-Up** with a write step.
- Show:
  - pending approval state
  - approval mode in activity metadata
  - action completion after approval

## 2:20 - 2:45 Guardrail block + trust proof

- Enable **Emergency write stop** in Security Controls.
- Re-run a write simulation (for example `gmail:send_email`) and show `global_write_kill_switch`.
- Click **Verify chain** and show receipt-chain status is `ok` with latest hash.
- Optionally open Activity details and point at `Receipt hash` + `Previous hash`.

## 2:45 - 3:00 Closing

- Summarize:
  - explicit permission boundaries
  - user consent and step-up approvals
  - production-aware checks and auditable activity timeline

## Recording tips

- Keep terminal and browser zoom readable.
- Use one continuous take if possible.
- Avoid copyrighted background music and logos you do not own.
