---
name: fix-defects
description: BA workflow Phase 8 step 8.4 — automated fix loop for CODE_DEFECT defects of one use case, at most 3 attempts per defect (D-26). Used by coding-agent; not for direct use.
user-invocable: false
---

# Step 8.4 — Automated Fix Loop

| | |
|---|---|
| Input | The defects listed in your prompt (`qa/defects/<UC>.md`: expected vs actual, test case, evidence); the approved spec; `technical/implementation/<UC>.md` |
| Output | Fix commits on the use case's branch; `fix_attempts` + 1 for each defect you worked on; the *Fix log* in the implementation summary |
| Consumers | QA retest (8.2, runs automatically because the summary changed); later the developer at GATE-10, once QA passes |

## Procedure

1. Work in the use case's worktree (`<repo>-worktrees/<UC>`). Fix only the defects in your prompt. Every one is classified CODE_DEFECT and is under the attempt limit. Read its expected and actual behaviour, then reproduce it with its test case.
2. The **expected behaviour is the approved spec**. Change the code to match it. If you find that the spec itself is wrong or silent, don't fix anything for that defect. Report it so QA can reclassify it as a SPECIFICATION_GAP for the BA.
3. Make the smallest change that fixes the cause, and add a regression test named after the defect. Never edit the acceptance test files (`test_files`, D-38). Rerun the acceptance and affected test suites until green.
4. Commit: `fix(<UC>-DEF-01): <what was wrong>`.
5. In `ba-ai/qa/defects/<UC>.md`, raise `fix_attempts` by one for each defect you worked on. Leave `status` alone: QA sets FIXED or UNRESOLVED after the retest.
6. In the implementation summary:
   - add a *Fix log* row (defect, commit, files);
   - add the commit to `commits`, and any new file to `code_refs`;
   - update *Automated Test Results*.
7. `tools/ba stamp ba-ai/technical/implementation/<UC>.md` → `tools/ba validate`.

The fix loop runs before code review (D-37): no human is involved until QA passes, and the developer then reviews the final code once. One round fixes all the listed defects together.

## Checklist

- [ ] Only the listed defects were touched; no unrelated refactoring.
- [ ] Each fix has a regression test; `fix_attempts` was raised by exactly one.
- [ ] Defects that are really specification gaps are reported, not "fixed" by guessing.
