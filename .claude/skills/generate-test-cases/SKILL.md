---
name: generate-test-cases
description: BA workflow step 8.1 — BEFORE any code exists, write the test coverage for one use case from its approved spec (ba-ai/qa/test-cases/<UC>.md) and the executable acceptance tests in the use case's worktree, which the implementation must make pass (D-38). Used by qa-agent; not for direct use.
user-invocable: false
---

# Step 8.1 — Acceptance Tests First

| | |
|---|---|
| Input | `specifications/analysis/<UC>-acceptance.md`, `<UC>-activity.md` (VR/AF/EF), `specifications/use-cases/<UC>.md`, `technical/api/<UC>.md`, the prototype, the entities' lifecycles, *Testing Conventions* |
| Output | `ba-ai/qa/test-cases/<UC>.md` (TC-NNN); executable acceptance tests committed in the use case's worktree |
| Consumers | The coding agent (7, makes them pass and may not edit them), test execution (8.2), GATE-07, the graph (`TestCase VERIFIES AcceptanceCriterion`, `CodeRef TESTS UseCase`) |

Why first: the tests then come from the approved spec, not from the code. The coding agent gets a precise, executable definition of done, and QA stays independent of the implementation (D-38).

## Procedure

1. **Worktree.** For each repository the tests touch, create the use case's worktree if it doesn't exist (`delivery.repositories[].worktree` in the context package):
   `git -C <repo> worktree add <repo>-worktrees/<UC> -b ba/<UC>-<slug> main`
   Work only there.
2. **IDs**: each test case gets a global ID from `tools/ba next-id TC`. Never number them yourself; the validator rejects IDs that were never allocated. On revisions, keep the existing IDs.
3. **Coverage** (master §25), at least:
   - every acceptance criterion, verified by one or more TCs (the validator enforces this);
   - every VR (validation), AF (alternate flow) and EF (error flow);
   - every business rule, including a boundary case for each numeric or date rule;
   - each API: success, validation error, authorization denial;
   - permission: every actor that must *not* do this;
   - every state transition the use case causes, and the forbidden ones from the entity's lifecycle.
4. **Category**, one per test case: Functional, Validation, API, Integration, Regression, Permission, State Transition, Negative or Boundary.
5. **Write the executable tests now, against the approved contract**, since there is no code yet:
   - **API tests** use the exact paths, payloads, status codes and error bodies from `technical/api/<UC>.md`.
   - **UI tests (Playwright, D-34)** locate elements by role and accessible name, with the labels and messages from the approved UI and prototype: `getByRole('button', { name: 'Submit request' })`, `getByText('<exact message>')`. Never use CSS selectors or test IDs that don't exist yet.
   - Name each test `TC-012 <title>`. Mark a test `manual` in the document only when automation can't observe the result. Manual critical journeys go to GATE-07.
   - They fail now. That is expected. Make sure each one fails for the right reason (missing endpoint or screen), not for a broken test.
   - Commit in the worktree: `TC-012..TC-020: acceptance tests for <UC>`.
6. **Document.** Use the template. List every automated test file in `test_files`, and the commit per repository in `tests_commit`. The coding agent may not change those files, and QA checks this at 8.2.
7. `tools/ba stamp` → `tools/ba validate`.

## Template

````markdown
---
id: <UC>
artifact_type: test-cases
title: <use case name> — Test Cases
status: DRAFT
version: 1
baseline: TO_BE
origin: AI
test_files: ["CODE:<repo-name>/<path>", ...]
tests_commit: {REPO-001: "<sha>", REPO-002: "<sha>"}
relations:
  business_rules: [BR-...]
  apis: [API-...]
open_questions: []
updated_at: ""
---
# <UC> — <use case name>: Test Cases

## Test Cases

### TC-012 — Submit a valid request
- **Verifies:** <UC>-AC-01
- **Category:** Functional
- **Automation:** ui — `CODE:leave-management-web/e2e/uc-001.spec.ts`
- **Preconditions:** …
- **Steps:** 1. … 2. …
- **Expected:** <observable result: status, message text, data change, HTTP code>
- **Covers:** BR-001, <UC>-VR-02

## Coverage
| Item | Test cases |
|---|---|
| <UC>-AC-01 | TC-012 |
| BR-001 | TC-012, TC-015 |
````

## Checklist

- [ ] Every AC, VR, AF, EF and BR appears in Coverage with at least one TC.
- [ ] Every expected result comes from the approved spec; UI tests use roles and labels from the approved UI.
- [ ] `test_files` and `tests_commit` are filled in; TC IDs came from `tools/ba next-id TC`.
