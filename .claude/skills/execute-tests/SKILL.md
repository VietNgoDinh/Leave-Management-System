---
name: execute-tests
description: BA workflow Phase 8 steps 8.2–8.3 — run one use case's tests, compare actual with required behaviour, and classify every failure (ba-ai/qa/test-results/<UC>.md, ba-ai/qa/defects/<UC>.md). Used by qa-agent; not for direct use.
user-invocable: false
---

# Steps 8.2–8.3 — Execute Tests and Compare with Requirements

| | |
|---|---|
| Input | `qa/test-cases/<UC>.md`, the implementation summary (branch, how to run), *Testing Conventions*, the approved spec |
| Output | `ba-ai/qa/defects/<UC>.md` (when anything failed), then `ba-ai/qa/test-results/<UC>.md` |
| Consumers | `tools/ba next` (the fix loop routes on each defect's classification), the coding agent (8.4), the BA/QA at GATE-07, the user guide (9) |

## Procedure

1. Work in the use case's worktrees (`delivery.repositories[].worktree`). Start what the tests need with the baseline's commands, **on a free port**, because other use cases may be testing in parallel.
   - **Check that the acceptance tests are untouched (D-38):** `git -C <worktree> diff --stat <tests_commit> -- <files in test_files>`.
   - If the implementation changed them, restore them (`git -C <worktree> checkout <tests_commit> -- <file>`) and record a CODE_DEFECT "implementation edited acceptance test <file>". Then run.
2. **Run** every automated test case: unit, API, integration, and UI with Playwright from the frontend repository (`npx playwright test …`, D-34). Record per TC: PASSED, FAILED, NOT_RUN (manual) or BLOCKED.
3. **Compare (8.3)**: for every failure, write *Expected* (from the spec, citing AC, VR or BR) vs *Actual* (observed, with evidence such as the log line, response or screenshot path), and classify it:

   | Classification | When |
   |---|---|
   | CODE_DEFECT | The code contradicts the approved spec |
   | SPECIFICATION_GAP | The spec is silent, ambiguous or self-contradictory, so the right behaviour is a business decision |
   | TEST_ISSUE | The test itself is wrong: bad data, wrong selector, wrong expectation versus the spec |
   | ENVIRONMENT_ISSUE | Infrastructure, configuration or a dependency stops the test running properly |
   | UNRESOLVED | You can't tell which; a human must look |

4. **Defects file**: one defect per distinct cause, not per failing test.
   - `id`: `<UC>-DEF-01`, `-02`, … Never renumber.
   - Each has a `### <UC>-DEF-01 — <title>` section with Expected, Actual, Evidence and the classification reason.
   - New defects get `status: OPEN, fix_attempts: 0`.
5. **On a retest** (action REGENERATE), update every existing defect:
   - its test passes now → `status: FIXED`;
   - still failing CODE_DEFECT with `fix_attempts` at the limit (3, D-26) → `status: UNRESOLVED` (hand-off to a human);
   - otherwise it stays OPEN. Reclassify it if the evidence changed: a CODE_DEFECT the coding agent reported as a spec problem becomes SPECIFICATION_GAP.
6. **Outcome**:
   - `PASSED` — every automated TC passed and no defect is OPEN or UNRESOLVED;
   - `FAILED` — anything else that ran;
   - `BLOCKED` — the tests could not run at all, with `blocked_reason`.
   Set `executed_at` to the current UTC time.
7. Stamp the defects file first (`tools/ba stamp ba-ai/qa/defects/<UC>.md`), then the results (they record the defects file's hash). Then `tools/ba validate`.

## Templates

````markdown
---
id: <UC>
artifact_type: defects
title: <use case name> — Defects
status: DRAFT
version: 1
baseline: TO_BE
origin: AI
defects:
  - {id: <UC>-DEF-01, test_case: TC-012, classification: CODE_DEFECT, status: OPEN, fix_attempts: 0}
relations: {}
updated_at: ""
---
# <UC> — Defects

## Defects

### <UC>-DEF-01 — <title>
- **Test case:** TC-012
- **Expected:** … (<UC>-AC-01, BR-…)
- **Actual:** …
- **Evidence:** …
- **Classification:** CODE_DEFECT — <why>
````

````markdown
---
id: <UC>
artifact_type: test-results
title: <use case name> — Test Results
status: DRAFT
version: 1
baseline: TO_BE
origin: AI
outcome: FAILED
executed_at: "2026-10-02T10:00:00Z"
summary: {total: 14, passed: 12, failed: 1, not_run: 1}
relations: {}
updated_at: ""
---
# <UC> — Test Results

## Summary
<outcome, counts, defects by classification>

## Environment
| Repository | Branch / commit | Command |
|---|---|---|

## Results
| Test case | Category | Result | Notes |
|---|---|---|---|

## Requirement Comparison
| Defect | Expected (spec) | Actual | Classification |
|---|---|---|---|
````

## Checklist

- [ ] Every test case has a result row.
- [ ] Every failure maps to a defect with expected vs actual and an honest classification.
- [ ] No expected result was relaxed to make a test pass.
