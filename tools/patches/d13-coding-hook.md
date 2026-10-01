# Pending kit change — D-13 coding hook (addendum D-36)

`tools/ba_cli/hooks.py` and `.claude/settings.json` are protected: they can only be changed in a session started with `BA_MAINTENANCE=1 claude`. Milestone 2 built everything the coding hook needs (`tools/ba_cli/coding.py`, `tools/ba coding authorize|revoke|status`). These two edits switch it on.

Until they are applied, the orchestrator enforces the precondition itself (CLAUDE.md, hard rule 9): it delegates to `coding-agent` only after `tools/ba coding authorize <UC>` succeeds.

## 1. `tools/ba_cli/hooks.py` — block product-repo writes without authorization

```diff
@@ def pre_tool_use() -> int:
     if tool in WRITE_TOOLS:
         target = ti.get("file_path") or ti.get("notebook_path")
         if target:
             p = Path(target)
             p = (p if p.is_absolute() else cwd / p).resolve()
             if _under(p, paths.DECISIONS):
                 reason = decisions_msg
             elif not maintenance:
                 hit = next((k for k in KIT_FILES if p == (paths.ROOT / k).resolve()), None)
                 if hit:
                     reason = kit_msg.format(f=hit)
+            if reason is None:
+                from . import coding
+                ok, why = coding.write_allowed(p)
+                if not ok:
+                    reason = why
     elif tool == "Bash":
         cmd = ti.get("command") or ""
         if ALWAYS_DENY_BASH.search(cmd):
             reason = decisions_msg
         elif "reviews/decisions" in cmd and MUTATING.search(cmd):
             reason = decisions_msg
         elif not maintenance and MUTATING.search(cmd):
             hit = next((k for k in KIT_FILES_IN_BASH if k in cmd), None)
             if hit:
                 reason = kit_msg.format(f=hit)
+        if reason is None and MUTATING.search(cmd):
+            # Best effort (D-13): a mutating command run inside, or naming, a product repository or worktree.
+            from . import coding
+            here = cwd.resolve()
+            for _rid, name, rpath in coding.governed_roots():
+                if here == rpath or rpath in here.parents or str(rpath) in cmd or f"../{rpath.name}" in cmd:
+                    ok, why = coding.write_allowed(rpath)
+                    if not ok:
+                        reason = why
+                        break
```

## 2. `.claude/settings.json` — let Claude Code see the product repositories

Add each repository path from `ba-ai/workflow/repositories.yaml` (D-02), and its use-case worktrees folder `<path>-worktrees` (D-39):

```json
"permissions": {
  "allow": ["Bash(tools/ba:*)", "Bash(./tools/ba:*)"],
  "additionalDirectories": ["../leave-management-api", "../leave-management-api-worktrees",
                            "../leave-management-web", "../leave-management-web-worktrees"]
}
```

## Check after applying

```
.venv/bin/python -m unittest discover -s tools/tests
```
Then, in a normal session: ask Claude to write a file in a product repository for a use case whose GATE-06 isn't approved. The hook must deny it with the D-13 message.
