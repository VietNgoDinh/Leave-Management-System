---
name: implement-use-case
description: BA workflow Phase 7 step 7 — implement one approved use case in its own git worktree until the QA agent's acceptance tests pass, and write the implementation summary (ba-ai/technical/implementation/<UC>.md). Used by coding-agent; not for direct use.
user-invocable: false
---

# Step 7 — Implementation

| | |
|---|---|
| Input | Approved `specifications/use-cases/<UC>.md`, `technical/api/<UC>.md`, `technical/sequence/<UC>.md`, prototype `ui/prototypes/<UC>/`, the acceptance tests (`qa/test-cases/<UC>.md`, its `test_files`), `technical/architecture/architecture.md`, coding rules, security rules, the existing code; context package `delivery` section |
| Output | Code and unit tests on branch `ba/<UC>-<slug>`, in the use case's worktrees; `ba-ai/technical/implementation/<UC>.md` |
| Consumers | QA test execution (8.2), then the developer at GATE-10 (code review), the user guide (9), the graph (`CodeRef IMPLEMENTS UseCase`) |

## Procedure (master §24)

1. **Worktrees.** The QA agent created the use case's worktree (`<repo>-worktrees/<UC>`, branch `ba/<UC>-<slug>`) for each repository its tests touch. Create it the same way for any other repository you change:
   `git -C <repo> worktree add <repo>-worktrees/<UC> -b ba/<UC>-<slug> main`
   Work only in the worktrees, never in the main checkout: other use cases are built in parallel (D-39).
2. **Read the acceptance tests first.** They are the executable definition of done (D-38). Never edit a file listed in `test_files`. If a test contradicts the approved spec, note it as `TEST_ISSUE?` in your summary and implement the spec.
3. **Plan.** List the modules and files to change and why, mapped to the spec's flows and APIs. Note every place the work **crosses a service boundary**.
4. **Implement** the minimum necessary:
   - the APIs exactly as designed (paths, payloads, status codes, error body);
   - the validations exactly as the VR rules;
   - the screens as in the approved prototype, with its labels (the UI tests find elements by role and label);
   - the conventions in the coding rules.
   Never rewrite unrelated modules.
5. **Iterate until green.** Run the acceptance tests and your own unit tests, using the *Testing Conventions* commands. Start servers on a free port, because other use cases may be testing in parallel. Fix and rerun until they pass, or until a failure is a spec problem: then stop and report the SPECIFICATION_GAP.
6. **Validate** the build and lint. Fix the failures your change caused; report failures that already existed and don't fix them.
7. **Commit** in small steps. The message starts with the use case or acceptance criterion ID. Never push, merge or open a pull request unless the user asks (D-25).
8. **Summary**: write the document (template). `code_refs` lists every file you changed as `CODE:<repo-name>/<path>`.
9. `tools/ba stamp ba-ai/technical/implementation/<UC>.md` → `tools/ba validate`.

QA then runs everything independently (8.2). The developer reviews the code once, after QA passes (GATE-10, D-37).

## Template

````markdown
---
id: <UC>
artifact_type: implementation
title: <use case name> — Implementation
status: DRAFT
version: 1
baseline: TO_BE
origin: AI
repositories: [REPO-001, REPO-002]
branch: ba/<UC>-<slug>
worktrees: {REPO-001: "<path>", REPO-002: "<path>"}
commits: ["<sha> <message>", ...]
code_refs: ["CODE:<repo-name>/<path>", ...]
relations:
  apis: [API-...]
  screens: [SCR-...]
  entities_written: [ENT-...]
open_questions: []
updated_at: ""
---
# <UC> — <use case name>: Implementation

## Implementation Plan
| Spec element | Change | Repository / module |
|---|---|---|

## Repositories and Branch
| Repository | Worktree | Branch | Base | How to run locally |
|---|---|---|---|---|

## Changed Files
| File | Change | Traces to |
|---|---|---|

## Automated Test Results
| Repository | Command | Acceptance (passed/failed) | Unit (passed/failed) | Notes |
|---|---|---|---|---|

## Traceability
| Acceptance criterion | Code | Test |
|---|---|---|

## Deviations and Open Points
<Every difference from the spec, each as an open question or SPECIFICATION_GAP; any TEST_ISSUE? — or "None.">

### Fix log
<Filled by step 8.4: defect, commit, files>
````

## Checklist

- [ ] Work happened only in the use case's worktrees; no acceptance test file was edited.
- [ ] Every change traces to the use case or an acceptance criterion; nothing unrelated changed.
- [ ] The acceptance and unit tests ran with the baseline's commands; the results are recorded honestly.
- [ ] Nothing was pushed, merged or opened as a PR.
