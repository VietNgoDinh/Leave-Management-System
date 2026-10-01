---
name: design-technical-baseline
description: BA workflow Phase 6A for a new product — propose the technical architecture baseline (stack, architecture, repositories, API conventions, error handling, logging, testing, coding rules, security rules, design system) and register services and repositories, for SA approval at GATE-09. Used by technical-baseline-agent; not for direct use.
user-invocable: false
---

# Phase 6A — Technical Architecture Baseline (designed)

| | |
|---|---|
| Input | Product overview, applications, integrations, data model, requirements (non-functional ones especially), technical constraints in `requirements/raw/`; context package `TECH_BASELINE.yaml` |
| Output | `technical/architecture/architecture.md`, `technical/coding-rules/frontend.md`, `technical/coding-rules/backend.md`, `technical/security/security-rules.md`, `ui/design-system.md`; catalogs `technical/architecture/services.yaml` (SVC) and `workflow/repositories.yaml` (REPO) |
| Consumers | The SA at GATE-09; API design (5.5, follows the API conventions); prototypes (5.3, follow the design system); coding (7); QA (8, testing conventions); user-guide screenshots (9) |

## Procedure

1. **Facts first.** Collect every technical constraint the stakeholders stated (hosting, existing identity provider, mandated language, data residency, browsers) and cite each one. Everything else you write is a **proposal**.
2. **Mark proposals.** For each choice the material doesn't make, write: **Proposed — SA to confirm:** <choice> — <one-line rationale>; alternative: <option>. When the choice really matters (database, identity, hosting, integration style), also add a TECHNICAL open question whose `related` lists the SVC, APP, ENT or INT it concerns (or leave it empty), and list its ID in the document's `open_questions`. The SA's GATE-09 decision settles it.
3. **Services.** One per deployable unit or bounded module that owns data:
   `tools/ba catalog add services --data '{"name": "...", "responsibility": "...", "repository": "REPO-...", "entities": ["ENT-..."], "integrations": ["INT-..."]}'`
   Register the repositories first.
4. **Repositories.** Each product repository, kept separate and never merged (master §2.1). They live next to this workspace:
   `tools/ba catalog add repositories --data '{"name": "room-booking-api", "type": "backend", "status": "PLANNED", "path": "../room-booking-api", "description": "..."}'`
   The coding agent creates them later and sets `status: ACTIVE`.
5. **Write the documents** with the headings below. `tools/ba validate` checks them.
   - **Testing Conventions** must name, for each repository: the unit test command; the API or integration test command; and the UI and end-to-end tool — **Playwright, installed in the frontend repository** (`npm i -D @playwright/test`, `npx playwright install`) — with its run command. QA (8.2) and the user-guide screenshots (9) use exactly these commands.
   - **API Conventions**: base path and versioning, resource naming, casing, pagination, filtering, standard status codes, the error body, idempotency, and all-or-nothing multi-item operations.
6. Stamp `architecture.md` first, then the other four (they record its hash). Then `tools/ba validate`.

## Required headings

| Document | id | Headings |
|---|---|---|
| `technical/architecture/architecture.md` (`technical-architecture`) | ARCH | Technology Stack · Application Architecture · Repository Structure · API Conventions · Error Handling · Logging · Testing Conventions — add Database, Dependency Rules and Deployment when relevant |
| `technical/coding-rules/frontend.md` / `backend.md` (`coding-rules`) | CODING-FRONTEND / CODING-BACKEND | Conventions (naming, structure, state management, dependency rules, linting and formatting, commit message format `UC-007: …`) |
| `technical/security/security-rules.md` (`security-rules`) | SECURITY | Authentication · Authorization (role → permission matrix from the actors) · Data Protection (personal data, retention, encryption) · Audit |
| `ui/design-system.md` (`design-system`) | DESIGN-SYSTEM | Principles · Layout · Components · Patterns (forms, tables, dialogs, validation messages, empty/loading/error states). New products get a minimal default (D-27). |

Frontmatter for each (fill `id`, `artifact_type`, `title`):

```yaml
---
id: ARCH
artifact_type: technical-architecture
title: <product> — Technical Architecture
status: DRAFT
version: 1
baseline: TO_BE
origin: AI
open_questions: [Q-..., ...]
updated_at: ""
---
```

## Checklist

- [ ] Every stated constraint is cited; every other choice is marked as a proposal for the SA.
- [ ] Every application has a repository and every entity has an owning service.
- [ ] The testing conventions name runnable commands per repository, with Playwright in the frontend repository.
- [ ] The security rules cover every actor's permissions and every PERSONAL_DATA or SECURITY flagged use case.
