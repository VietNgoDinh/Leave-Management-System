"""Claude Code hooks that keep gate decisions human-only (D-10).

- user-prompt:  UserPromptSubmit. When the *user* types /ba-approve or /ba-changes,
                the decision is recorded here, before the model sees the prompt.
- pre-tool-use: PreToolUse. Blocks the model from writing decision records or the
                files that enforce the gates (unless BA_MAINTENANCE=1).
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from . import gates, paths
from .ids import GATE_RE, normalize_id
from .store import BAError
from .workspace import Workspace

PROMPT_RE = re.compile(r"^\s*/ba-(approve|changes)(?:\s+(.*))?\s*$", re.S | re.I)
DECISIONS = {"approve": "APPROVED", "changes": "CHANGES_REQUESTED"}
USAGE = "usage: /ba-approve <SUBJECT> <GATE-ID> [comment]  or  /ba-changes <SUBJECT> <GATE-ID> <comments>"

WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
KIT_FILES = (".claude/settings.json", ".claude/settings.local.json", "tools/ba",
             "tools/ba_cli/hooks.py", "tools/ba_cli/gates.py")
KIT_FILES_IN_BASH = KIT_FILES[:2] + KIT_FILES[3:]
ALWAYS_DENY_BASH = re.compile(r"\bba\s+decide\b|\bhook\s+user-prompt\b|\brecord_decision\b")
MUTATING = re.compile(r">|\bsed\s+-i|\btee\b|\bmv\b|\bcp\b|\brm\b|\bperl\s+-i|\bpython\d?\b|"
                      r"\btruncate\b|\bchmod\b|\bln\b|\bdd\b|\binstall\b")


def reviewer_name() -> str:
    try:
        out = subprocess.run(["git", "config", "user.name"], cwd=str(paths.ROOT),
                             capture_output=True, text=True, timeout=5).stdout.strip()
        if out:
            return out
    except Exception:
        pass
    return os.environ.get("USER") or "unknown"


def parse_decision_args(rest: str):
    tokens = (rest or "").split(None, 2)
    if len(tokens) < 2:
        raise BAError(USAGE)
    a, b = normalize_id(tokens[0]), normalize_id(tokens[1])
    if GATE_RE.match(b):
        subject, gate = a, b
    elif GATE_RE.match(a):
        gate, subject = a, b
    else:
        raise BAError(USAGE)
    return subject, gate, tokens[2] if len(tokens) > 2 else ""


def user_prompt_submit() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    m = PROMPT_RE.match(data.get("prompt") or "")
    if not m:
        return 0
    decision = DECISIONS[m.group(1).lower()]
    reviewer = reviewer_name()
    try:
        subject, gate, comments = parse_decision_args(m.group(2))
        f = gates.record_decision(Workspace(), gate, subject, decision, comments, reviewer,
                                  "UserPromptSubmit hook (typed by the user)")
    except BAError as e:
        print(f"BA gate: decision NOT recorded — {e}", file=sys.stderr)
        return 2
    msg = (f"[BA gate hook] Recorded {decision} for {gate} on {subject} by {reviewer} "
           f"→ ba-ai/{paths.rel(f)}. This decision was typed by the human user.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                             "additionalContext": msg}}))
    return 0


def _under(p: Path, root: Path) -> bool:
    try:
        p.relative_to(root.resolve())
        return True
    except ValueError:
        return False


def pre_tool_use() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    cwd = Path(data.get("cwd") or os.getcwd())
    maintenance = os.environ.get("BA_MAINTENANCE") == "1"
    reason = None
    decisions_msg = ("Gate decisions are recorded only when the human types /ba-approve or /ba-changes. "
                     "Claude must never create or edit them.")
    kit_msg = ("{f} enforces the approval gates and is protected. Edit it only in maintenance mode "
               "(the user starts Claude Code with BA_MAINTENANCE=1).")

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

    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                 "permissionDecision": "deny",
                                                 "permissionDecisionReason": reason}}))
    return 0
