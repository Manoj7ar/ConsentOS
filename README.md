# ConsentOS

ConsentOS is a policy and approval layer for agent actions over real user accounts. It keeps provider tokens in Auth0 Token Vault, exchanges short-lived access only at execution time, and forces high-risk writes through explicit approval.

The repo contains:

- `backend/`: FastAPI policy, activity, approval, and connected-account API
- `mcp/`: provider MCP servers and the built-in workflow orchestrator
- `frontend/`: Next.js dashboard, chat UI, readiness view, and approval polling

## Supported Workflows

- `invoice_collections`: read overdue invoice signals from Gmail, cross-check Calendar, draft follow-up emails, and create Stripe payment links after confirmation
- `calendar_follow_up`: review upcoming meetings or schedule a follow-up meeting after required details are present
- `slack_to_github_escalation`: review recent Slack mentions, draft an incident issue, open it in GitHub, and optionally post a Slack acknowledgement
- `github_issue_review`: review open issues for a repository without taking write actions

## Strict Live Run

ConsentOS now defaults to strict live mode. The primary path assumes:

- no development auth headers
- no mock connected accounts
- no mock token-vault exchange
- no demo auto-approval fallback
- a non-placeholder `INTERNAL_API_SHARED_SECRET`

If those conditions are not met, `/health/ready`, `/api/auth/diagnostics`, and the chat UI will surface blocking checks and live execution will stay disabled.

## Fastest Setup

If you want the repo to do the boring parts for you, use the bootstrap helper:

```powershell
.\scripts\setup.ps1
```

Or:

```bash
python scripts/bootstrap_env.py
```

That will:

- create or update `.env` from `.env.example`
- generate `INTERNAL_API_SHARED_SECRET`
- generate `AUTH0_SECRET`
- mirror `BACKEND_AUTH0_DOMAIN` and `BACKEND_AUTH0_ISSUER` from `AUTH0_DOMAIN` when possible
- print the exact remaining values you still need to paste manually

You can also prefill values while bootstrapping:

```powershell
.\scripts\setup.ps1 --set AUTH0_DOMAIN=your-tenant.us.auth0.com --set MCP_GEMINI_API_KEY=your-gemini-key
```

### 1. Copy config

```bash
cp .env.example .env
```

### 2. Configure Auth0

- create an Auth0 Regular Web App for the frontend browser session
- create an Auth0 Machine-to-Machine app for backend Token Vault exchange
- configure Auth0 CIBA for approval
- enable Connected Accounts / Token Vault for Google, GitHub, Stripe, and Slack
- make sure each connected account has the provider scopes needed by the workflows you want to run

Required frontend envs:

- `AUTH0_DOMAIN`
- `AUTH0_CLIENT_ID`
- `AUTH0_CLIENT_SECRET`
- `AUTH0_SECRET`
- `APP_BASE_URL`

Required backend envs for strict live execution:

- `INTERNAL_API_SHARED_SECRET`
- `BACKEND_AUTH0_DOMAIN`
- `BACKEND_AUTH0_CLIENT_ID`
- `BACKEND_AUTH0_CLIENT_SECRET`
- `BACKEND_AUTH0_CIBA_CLIENT_ID`
- `BACKEND_AUTH0_CIBA_CLIENT_SECRET`

Required orchestrator envs:

- `MCP_GEMINI_API_KEY`
- provider-specific settings such as `MCP_SLACK_MENTION_CHANNEL_IDS`

### 3. Start the stack

```bash
docker-compose up --build
```

Or run services manually:

```bash
cd backend
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

```bash
cd mcp
pip install -e .
uvicorn consentos_mcp.orchestrator.runtime:app --host 0.0.0.0 --port 8100
```

```bash
cd frontend
npm install
npm run dev
```

### 4. Verify readiness

```bash
curl http://localhost:8000/health/ready
curl http://localhost:8100/health/ready
```

The dashboard will also show blocking checks and refuse live execution until they are cleared.

## Main Demo Flow

1. Log into the Next.js app with Auth0.
2. Confirm the Auth0 status card is `ok` and strict live mode is enabled.
3. Connect Google, GitHub, Stripe, and Slack through Auth0 Connected Accounts.
4. Let the dashboard sync connected-account metadata into the backend.
5. Run one of the supported workflows in chat.
6. Confirm the proposed write actions.
7. Approve any high-risk step-up actions on your phone.
8. Review the activity timeline for receipts and final status.

## Notes

- Next.js owns the browser Auth0 session and forwards a trusted subject token to the backend and orchestrator for live Token Vault exchange.
- The backend stores connected-account metadata, permissions, and activity receipts; provider access tokens remain in Auth0 Token Vault.
- `BACKEND_ALLOW_MOCK_CONNECTED_ACCOUNTS`, `BACKEND_ALLOW_MOCK_TOKEN_VAULT`, and `BACKEND_AUTO_APPROVE_WHEN_CIBA_UNAVAILABLE` still exist for explicit developer fallback use, but strict live mode treats them as blocking.
- Slack mention scanning depends on `MCP_SLACK_MENTION_CHANNEL_IDS`.
- The workflow router uses the configured Gemini model when `MCP_GEMINI_API_KEY` is present and falls back to deterministic intent matching otherwise.
