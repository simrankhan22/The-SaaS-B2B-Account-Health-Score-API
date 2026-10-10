---
schema: clarification-answers/v1
status: submitted
generated_at: "2026-10-10T17:31:48.975Z"
scope: [backend, generic]
questions_file: clarification-questions.json
---

# Rearchitecture Clarification Answers

## ⚙️ Backend

- **B1** You specified FastAPI. Which FastAPI and Python versions should the project target?
  - answer: FastAPI (version not specified)
  - source: user
- **B2** If request or response shapes change after launch, how should the API handle compatibility?
  - answer: can break with versioning
  - source: user
- **B3** What should the initial service use to persist account profiles, usage metrics, and scoring results?
  - answer: PostgreSQL with a new schema
  - source: user
- **B4** What authentication and authorization should protect scoring endpoints and batch results?
  - answer: preserve existing auth mechanism; detect from codebase
  - source: user
- **B5** What response-time and batch-completion targets should the service meet (for example, p95 latency for /predict and time to score 1,000 accounts)?
  - answer: im not sure
  - source: user

## 📋 General

- **G1** What measurable acceptance criteria would make this project successful? Consider model quality, endpoint behavior, batch completion, documentation, and deployment readiness.
  - answer: im not sure, u recomment
  - source: user
- **G2** What should the first version explicitly leave out (for example, customer-facing UI, CRM integrations, model training, or automatic retention actions)?
  - answer: not sure
  - source: user
- **G3** How should tests be handled as the project is built?
  - answer: must pass
  - source: user
- **G5** Add any other constraints, requirements, exclusions, compliance rules, or dependencies not covered above.
  - answer: None beyond the decisions listed in this specification.
  - source: user
