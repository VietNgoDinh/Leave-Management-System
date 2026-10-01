"""Coding authorization (addendum D-13, D-25).

Code may be written in a product repository only for a use case whose GATE-05 (BA spec) and GATE-06
(technical approval) are APPROVED, while the run's GATE-09 (technical baseline) is APPROVED.
`tools/ba coding authorize <UC>` checks this and records the use case in
`state.json.coding_authorization`; `write_allowed()` is what the PreToolUse hook asks before a
Write/Edit lands in a product repository. Gates are re-checked live on every call, so an approval
that is invalidated later revokes the authorization at once.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional, Tuple

from . import paths, store
from .ids import normalize_id
from .store import BAError

UC_GATES = ("GATE-05", "GATE-06")
RUN_GATES = ("GATE-09",)


def problems(ws, gs: Callable, uc: str) -> List[str]:
    out = []
    if ws.catalog_of(uc) != "use-cases":
        return [f"{uc} is not a use case"]
    run = ws.active_run()
    if not run:
        return ["no active run in workflow/state.json"]
    for g in RUN_GATES:
        s = gs(g, run["run_id"])["status"]
        if s != "APPROVED":
            out.append(f"{g} on {run['run_id']} is {s}")
    for g in UC_GATES:
        s = gs(g, uc)["status"]
        if s != "APPROVED":
            out.append(f"{g} on {uc} is {s}")
    return out


def authorized(ws) -> List[str]:
    return list((ws.state.get("coding_authorization") or {}).get("use_cases") or [])


def repositories(ws=None) -> List[Tuple[str, str, Path]]:
    """(REPO id, name, resolved path) for every repository with a path. Without a workspace it reads only
    workflow/repositories.yaml, so the PreToolUse hook stays cheap."""
    if ws is not None:
        items = ws.items_in("repositories")
    else:
        f = paths.BA / "workflow" / "repositories.yaml"
        items = ((store.load_yaml(f) or {}).get("items") or []) if f.exists() else []
    out = []
    for r in items:
        if isinstance(r, dict) and r.get("path"):
            p = Path(r["path"])
            out.append((r["id"], r.get("name") or r["id"], (p if p.is_absolute() else paths.ROOT / p).resolve()))
    return out


def worktrees_root(repo_path: Path) -> Path:
    """Use-case worktrees of a repository live next to it: ../<repo>-worktrees/<UC>/ (D-39)."""
    return repo_path.parent / f"{repo_path.name}-worktrees"


def worktree_path(repo_path: Path, uc: str) -> Path:
    return worktrees_root(repo_path) / uc


def governed_roots(ws=None) -> List[Tuple[str, str, Path]]:
    """Every directory a product-repository write can land in: each repository and its worktrees root."""
    out = []
    for rid, name, p in repositories(ws):
        out += [(rid, name, p), (rid, name, worktrees_root(p))]
    return out


def repo_for(target: Path, ws=None) -> Optional[Tuple[str, str, Path]]:
    target = Path(target).resolve()
    return next((r for r in governed_roots(ws) if target == r[2] or r[2] in target.parents), None)


def repositories_ready(ws) -> Tuple[bool, List[str]]:
    """D-39: tests and code need every product repository created (status ACTIVE, path on disk)."""
    repos = ws.items_in("repositories")
    if not repos:
        return False, ["no product repositories are registered in workflow/repositories.yaml "
                       "(the technical baseline lists them)"]
    paths_ = {rid: p for rid, _n, p in repositories(ws)}
    why = []
    for r in repos:
        p = paths_.get(r["id"])
        if p is None:
            why.append(f"{r['id']} {r.get('name')} has no path")
        elif r.get("status") != "ACTIVE" or not p.exists():
            why.append(f"{r['id']} {r.get('name')} is {r.get('status')}"
                       + ("" if p.exists() else f" and {p} does not exist yet"))
    return not why, why


def authorize(uc_arg: str) -> dict:
    from .engine import GateCache
    from .workspace import Workspace
    uc = normalize_id(uc_arg)
    with store.locked():
        ws = Workspace()
        probs = problems(ws, GateCache(ws), uc)
        if probs:
            raise BAError(f"coding is not authorized for {uc}: " + "; ".join(probs))
        state = store.load_json(paths.STATE)
        auth = state.get("coding_authorization") or {}
        ucs = sorted(set(auth.get("use_cases") or []) | {uc})
        state["coding_authorization"] = {"use_cases": ucs, "updated_at": store.now()}
        state["updated_at"] = store.now()
        store.save_json(paths.STATE, state)
    return {"use_case": uc, "authorized": ucs,
            "repositories": [{"id": i, "name": n, "path": str(p), "exists": p.exists(),
                              "worktree": str(worktree_path(p, uc))}
                             for i, n, p in repositories(ws)]}


def revoke(uc_arg: Optional[str] = None) -> List[str]:
    with store.locked():
        state = store.load_json(paths.STATE)
        auth = state.get("coding_authorization") or {}
        ucs = [] if uc_arg is None else [u for u in auth.get("use_cases") or [] if u != normalize_id(uc_arg)]
        state["coding_authorization"] = {"use_cases": ucs, "updated_at": store.now()} if ucs else None
        state["updated_at"] = store.now()
        store.save_json(paths.STATE, state)
    return ucs


def prune(ws, gs: Callable) -> bool:
    """Drop authorizations that no longer hold, or are no longer needed (the use case is delivered:
    GATE-08 approved). Edits ws.state in place; the caller saves it. Returns True when something changed."""
    ucs = authorized(ws)
    keep = [uc for uc in ucs if not problems(ws, gs, uc) and gs("GATE-08", uc)["status"] != "APPROVED"]
    if keep == ucs:
        return False
    ws.state["coding_authorization"] = {"use_cases": keep, "updated_at": store.now()} if keep else None
    return True


def write_allowed(target: Path, ws=None) -> Tuple[bool, Optional[str]]:
    """Should a Write/Edit to `target` be allowed? Only product-repository paths are governed."""
    from .engine import GateCache
    from .workspace import Workspace
    target = Path(target).resolve()
    try:
        target.relative_to(paths.ROOT)
        return True, None                      # the BA workspace itself is governed by the other rules
    except ValueError:
        pass
    repo = repo_for(target, ws)
    if repo is None:
        return True, None
    ws = ws or Workspace()
    gs = GateCache(ws)
    valid = [uc for uc in authorized(ws) if not problems(ws, gs, uc)]
    if valid:
        return True, None
    return False, (f"{repo[1]} ({repo[0]}) is a product repository. Code may be written only for a use case "
                   f"whose GATE-05 and GATE-06 are APPROVED, with GATE-09 APPROVED (addendum D-13). "
                   f"Run `tools/ba coding authorize <UC>` first; it refuses until those gates pass.")
