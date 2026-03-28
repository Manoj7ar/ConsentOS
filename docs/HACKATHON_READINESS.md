# Hackathon Readiness Checklist

Use this list to move from "working prototype" to "judge-ready submission."

## Submission requirements (Devpost)

- [ ] Public 3-minute demo video uploaded (YouTube, Vimeo, etc.)
- [ ] Published project/application link provided
- [ ] Repository URL added
- [ ] Team member info complete

## Setup and reproducibility

- [ ] `.env` generated from `.env.example` and required keys filled
- [ ] `make check-ready` returns passing results
- [ ] `docker-compose up --build` starts all services
- [ ] `http://localhost:8000/health/ready` reports expected checks
- [ ] `http://localhost:8100/health/ready` reports expected checks

## Quality gates

- [ ] Backend tests pass
- [ ] MCP tests pass
- [ ] Frontend lint passes
- [ ] Frontend typecheck passes
- [ ] Frontend build succeeds

## Security and policy demo proof points

- [ ] Show strict-live diagnostics panel and explain blocking checks
- [ ] Show connected-account sync from Auth0
- [ ] Show a low-risk read action that runs without approval
- [ ] Show a high-risk write action that requires approval
- [ ] Show policy simulator reason codes for allowed, blocked, and approval-required paths
- [ ] Show temporary delegated consent on a single tool (time-boxed approval window)

## Demo polish

- [ ] Use the "Judge Mode" prompt sequence in the UI
- [ ] Keep narration focused on user control and explicit boundaries
- [ ] Include one intentional blocked action to prove guardrails
- [ ] End with receipts/activity timeline and final status

## Recommended talk track for judges

1. Tokens stay in Auth0 Token Vault, not in app storage.
2. Policy checks run before provider API calls.
3. High-risk actions require explicit CIBA approval.
4. Temporary delegated consent can reduce approval spam while staying time-bounded.
5. Every action emits activity metadata and approval context for auditability.
