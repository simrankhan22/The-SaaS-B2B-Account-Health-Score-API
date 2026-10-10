---
schema: clarification/v1
generated_at: "2026-10-10T17:32:23Z"
scope:
  - backend
  - generic
clarity_score: 0.75
rounds: 1
gaps:
  - nfr.sla
  - success.definition
  - out_of_scope
blocking_gaps: []
---

# Scenario Clarification

## Backend

- **Target framework**: Python 3.12 with FastAPI (pin a compatible FastAPI release in the dependency manifest).
- **API contract preservation**: can break with versioning.
- **Data migration strategy**: PostgreSQL with a new schema.
- **Auth framework**: preserve existing auth mechanism; detect from codebase.
- **SLA targets**: Recommended starting target (not confirmed): `/predict` p95 latency under 250 ms and scoring 1,000 accounts within 60 seconds, measured separately from upload/queue time.

## Generic

- **Success definition**: Recommended working definition (not confirmed): `/predict` returns a documented, calibrated churn probability and High/Medium/Low tier for valid accounts; `/batch-scoring` accepts CSV and JSON batches of at least 1,000 accounts, processes them asynchronously, and exposes each job's status and results; validation, error handling, tests, and API documentation are complete.
- **Out of scope**: No customer-facing UI, CRM integration, or automatic customer outreach/retention actions in the first version.
- **Existing test posture**: must pass.
- **Additional constraints**: None beyond the decisions listed in this specification.

---

## Gaps & Defaults Applied

- id: nfr.sla
  resolution: default
  default_used: "Recommended starting target (not confirmed): /predict p95 under 250 ms; score 1,000 accounts within 60 seconds, excluding queue/upload time."
  note: "The user was unsure; targets are proposed for discussion and should be validated against deployment capacity and model choice."
- id: success.definition
  resolution: default
  default_used: "Recommended working definition covering calibrated single-account scoring, asynchronous 1,000+ account batches with job status/results, validation, tests, and documentation."
  note: "The user requested a recommendation; acceptance criteria are proposed, not confirmed."
- id: out_of_scope
  resolution: default
  default_used: "No customer-facing UI, CRM integration, or automatic customer outreach/retention actions in the first version."
  note: "The user was unsure; exclusions are inferred from the API-focused brief."

## Downstream Usage Notes

- Treat the proposed SLA, success criteria, and out-of-scope items as working assumptions, not confirmed requirements.
- Python 3.12 is user-confirmed. Pin a compatible FastAPI release during implementation.
- Items listed under "Gaps & Defaults Applied" were not explicitly confirmed by the user. Treat them as working assumptions and flag them if they affect critical design decisions.
- No required blocking gaps remain.
- Do NOT re-ask the user about items that are fully answered (non-gap) in this file — they count as resolved and do not consume `[NEEDS CLARIFICATION]` budget in the spec phase.
