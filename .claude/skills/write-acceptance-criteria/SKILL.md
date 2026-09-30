---
name: write-acceptance-criteria
description: BA Spec Engine step 5.7 — testable Given/When/Then acceptance criteria covering the main flow, every rule, validation, alternate and error flow (ba-ai/specifications/analysis/<UC>-acceptance.md). Used by spec-agent; not for direct use.
user-invocable: false
---

# Step 5.7 — Acceptance Criteria

| | |
|---|---|
| Input | UI markdown, API design, activity/validation analysis, context package |
| Output | `ba-ai/specifications/analysis/<UC>-acceptance.md` |
| Consumers | Compiled spec (5.8), QA test cases (TC VERIFIES AC), coding agent |

## Rules

- One criterion per observable behaviour: `### <UC>-AC-01 — <title>` followed by **Given / When / Then** lines (validation fails without all three).
- **Testable:** concrete data and observable results — status, message text, data change, HTTP code. Never "works correctly", "is fast", "user-friendly".
- End each criterion with `**Covers:**` listing what it verifies: main flow step, BR-…, <UC>-VR-…, <UC>-AF-…, <UC>-EF-….
- **Coverage is complete:** the main flow; every business rule in the use case; every VR, AF and EF from the activity analysis; permission denial; at least one boundary case per numeric or format rule.
- IDs are stable: on revisions keep existing numbers and append new ones.
- Only behaviour defined upstream. If writing a criterion exposes a gap, add an open question instead of deciding.

## Template

````markdown
---
id: <UC>
artifact_type: acceptance-criteria
title: <use case name> — Acceptance Criteria
status: DRAFT
version: 1
baseline: TO_BE
origin: AI
relations:
  business_rules: [<BR>, ...]
  screens: [<SCR>, ...]
  apis: [<API>, ...]
open_questions: []
updated_at: ""
---
# <UC> — <use case name>: Acceptance Criteria

## Acceptance Criteria

### <UC>-AC-01 — <title>
- **Given** …
- **When** …
- **Then** …
- **Covers:** main flow, BR-…, <UC>-VR-01

## Coverage
| Item | Covered by |
|---|---|
| BR-… | <UC>-AC-01 |
| <UC>-VR-01 | <UC>-AC-02 |
| <UC>-AF-01 | <UC>-AC-03 |
| <UC>-EF-01 | <UC>-AC-04 |
````

Every BR in `relations.business_rules` and every VR/AF/EF declared in the activity analysis must appear in the Coverage table with at least one criterion.
