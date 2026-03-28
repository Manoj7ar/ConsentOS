# Threat Model and Judging Criteria Map

This document maps ConsentOS controls to common hackathon judging dimensions and explicit attacker scenarios.

## 1) Threat model (practical)

### Assets

- User delegated authority across providers (Google, GitHub, Stripe, Slack)
- Approval state and activity audit history
- Policy controls for allowed/blocked tools

### Trust boundaries

- Browser session boundary (Next.js + Auth0 session)
- Backend policy boundary (FastAPI policy/approval/activity APIs)
- Provider boundary (downstream APIs invoked only after policy/approval)

### High-probability abuse scenarios

1. **Agent prompt triggers unintended writes**
   - Mitigations: per-tool policy gates, risk-based approval, emergency write-control endpoint
2. **Approval replay beyond intended duration**
   - Mitigations: delegated approval windows with explicit TTL metadata (`approved_until`)
3. **Tampering with activity history to hide actions**
   - Mitigations: hash-linked receipt chain with verification endpoint
4. **Silent high-impact execution without user visibility**
   - Mitigations: activity timeline with policy decision metadata and request identifiers

### Residual risk (explicit)

- Control quality depends on accurate tool risk classification.
- If operator leaves write control disabled during a live incident, harm is still possible.
- Receipt chain proves integrity of stored log history, not business correctness of tool outputs.

## 2) Control-to-criterion mapping

### Security model / trust

- **Tamper-evident receipt chain**: `/api/security/receipt-chain/verify`
- **Emergency write stop**: `/api/security/write-control`
- **Policy simulation with reason codes**: `/api/permissions/simulate`

### User control and consent

- **Per-tool allow/deny policy**: `/api/permissions`
- **Step-up approval requirement** for high-risk actions
- **Delegated approval windows** for bounded consent reuse

### Technical execution quality

- End-to-end backend APIs for policy, approval, activity, and security verification
- Frontend controls for write stop, receipt verification, and blast-radius visibility
- Automated tests covering write-stop and blast-radius behavior

### UX clarity / explainability

- Simulator explanation + reason codes + blast radius preview
- Activity detail includes receipt hash linkage and request metadata

### Impact and insight

- Demonstrates actionable controls for "agentic delegation with guardrails"
- Shows measurable safety posture in demo, not just claims

## 3) Demo checkpoints for judges

1. Show **strict-live readiness** and connected account state.
2. Run policy simulation for a write tool and explain blast radius.
3. Enable emergency write stop and rerun simulation to show hard block.
4. Verify receipt chain and show latest hash.
5. Show activity row with receipt hash / previous hash details.
