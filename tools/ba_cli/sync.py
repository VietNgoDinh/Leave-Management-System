"""`ba sync` and `ba stamp`: recompute every derived status and record artifact inputs."""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from . import gates, graph, paths, schema, store, views
from .engine import GateCache, derive_run, derive_uc
from .ids import as_list, prefix_of
from .store import BAError
from .validate import errors_by_rel, validate
from .workspace import Doc, Workspace

LATER_STAGE_FIELDS = ("technical_review_status", "coding_status", "testing_status", "documentation_status")


# ------------------------------------------------------------------ stamping (D-12)

def stamp_doc(ws: Workspace, doc: Doc) -> List[dict]:
    """Record the exact inputs (and their hashes) this document was built from."""
    entries: List[dict] = []
    step = schema.step_for_type(doc.type)
    if step:
        for t in step.get("built_from", []):
            irel = ws.input_rel(t, doc.id)
            h = ws.hash_rel(irel)
            if h is None:
                raise BAError(f"cannot stamp ba-ai/{doc.rel}: its input ba-ai/{irel} does not exist yet")
            entries.append({"path": irel, "hash": h})
    prefixes = set(schema.artifacts()["stamp_ref_prefixes"])
    refs = [doc.id]
    for vals in (doc.fm.get("relations") or {}).values():
        refs += as_list(vals)
    refs += as_list(doc.fm.get("open_questions")) + as_list(doc.fm.get("assumptions"))
    seen = set()
    for ref in refs:
        if ref in seen or prefix_of(str(ref)) not in prefixes:
            continue
        seen.add(ref)
        h = ws.item_hash(ref)
        if h:
            entries.append({"ref": ref, "hash": h})
    doc.write_fm({"built_from": entries, "updated_at": store.now()})
    return entries


# ------------------------------------------------------------------ derived statuses

def coverage(ws: Workspace) -> Dict[str, List[tuple]]:
    cov: Dict[str, List[tuple]] = {}
    for gid, subj in gates.instances(ws):
        for rel in gates.artifact_rels(gid, subj):
            cov.setdefault(rel, []).append((gid, subj))
    return cov


def covering(cov: Dict[str, List[tuple]], rel: str) -> List[tuple]:
    out = list(cov.get(rel, []))
    for r, entries in cov.items():
        if r.endswith("/") and rel.startswith(r):
            out += entries
    return out


def _artifact_status(gs: Callable, entries: List[tuple], stale: bool, current: Optional[str]) -> Optional[str]:
    if stale:
        return "STALE"
    if not entries:
        return "DRAFT" if current == "STALE" else current
    ss = [gs(g, s)["status"] for g, s in entries]
    if "WAITING" in ss:
        return "WAITING_FOR_REVIEW"
    if "CHANGES_REQUESTED" in ss:
        return "CHANGES_REQUESTED"
    if all(x == "APPROVED" for x in ss):
        return "APPROVED"
    return "DRAFT"


def stage_status(ws: Workspace, gs: Callable, uc: str, types: List[str], gate_ids: List[str]) -> str:
    docs = [ws.docs.get(ws.doc_rel(t, uc)) for t in types]
    if all(d is None for d in docs):
        return "NOT_STARTED"
    if any(d is not None and ws.stale_reasons(d) for d in docs):
        return "STALE"
    ss = [gs(g, uc)["status"] for g in gate_ids]
    if all(s == "APPROVED" for s in ss):
        return "APPROVED"
    for s, label in (("WAITING", "WAITING_FOR_REVIEW"), ("CHANGES_REQUESTED", "CHANGES_REQUESTED"),
                     ("BLOCKED", "BLOCKED")):
        if s in ss:
            return label
    return "IN_PROGRESS"


def step_label(r: dict) -> str:
    return {"ACTION": r.get("step"), "WAITING": r.get("gate"), "DONE": "SPEC_APPROVED",
            "NOT_READY": "NOT_STARTED"}.get(r["state"], "BLOCKED")


def step_note(r: dict) -> str:
    if r["state"] == "ACTION":
        if r["action"] == "REQUEST_GATE":
            return f"request {r['gate']} review"
        return f"{r['action']} {r['step_name']}"
    if r["state"] == "WAITING":
        return f"waiting for human review ({r['gate']})"
    if r["state"] == "DONE":
        return "BA spec approved (GATE-05); technical review is not in milestone 1"
    return r.get("reason") or ""


def run_sync() -> dict:
    with store.locked():
        ws = Workspace()
        issues = validate(ws)
        errs = errors_by_rel(issues)
        gs = GateCache(ws)
        cov = coverage(ws)
        changed = {"docs": 0, "catalogs": 0, "backlog": False, "state": False, "graph": False}

        for doc in ws.docs.values():
            entries = covering(cov, doc.rel)
            new = _artifact_status(gs, entries, bool(ws.stale_reasons(doc)), doc.fm.get("status"))
            review = {g: gs(g, s)["status"] for g, s in entries} or None
            upd = {}
            if new and new != doc.fm.get("status"):
                upd["status"] = new
            if review != doc.fm.get("review") and (review or "review" in doc.fm):
                upd["review"] = review
            if upd:
                doc.write_fm(upd)
                changed["docs"] += 1

        for cname, data in ws.catalog_data.items():
            rel = schema.catalogs()[cname]["path"]
            entries = covering(cov, rel)
            if not entries:
                continue
            meta = data.setdefault("meta", {})
            new = _artifact_status(gs, entries, False, meta.get("status"))
            review = {g: gs(g, s)["status"] for g, s in entries}
            if meta.get("status") != new or meta.get("review") != review:
                meta["status"], meta["review"] = new, review
                store.save_yaml(paths.BA / rel, data)
                changed["catalogs"] += 1

        run = ws.active_run()
        stages = schema.engine()["stages"]
        for uc, rec in ws.backlog_ucs.items():
            item = rec["item"]
            r = derive_uc(ws, uc, run, gs, errs)
            upd = {}
            cat = ws.item(uc) or {}
            for f in ("name", "application", "actor", "complexity", "risk_level"):
                if cat.get(f) is not None:
                    upd[f] = cat[f]
            upd["current_step"] = step_label(r)
            upd["workflow_note"] = step_note(r)
            for field, sdef in stages.items():
                upd[field] = stage_status(ws, gs, uc, sdef["artifact_types"], sdef["gates"])
            # Stages with no engine yet: give a new backlog item their starting value, never overwrite one.
            for field in LATER_STAGE_FIELDS:
                if field not in stages and item.get(field) is None:
                    upd[field] = "NOT_STARTED"
            for field, t in (("ui_artifact", "ui-markdown"), ("spec_artifact", "use-case-specification"),
                             ("technical_artifact", "api-design")):
                rel = ws.doc_rel(t, uc)
                upd[field] = paths.show(rel) if rel in ws.docs else None
            started = any(ws.doc_rel(s["artifact_type"], uc) in ws.docs for s in schema.engine_steps())
            if item.get("status") == "READY" and started:
                upd["status"] = "IN_PROGRESS"
            for k, v in upd.items():
                if item.get(k) != v:
                    item[k] = v
                    changed["backlog"] = True
        if changed["backlog"]:
            store.save_yaml(paths.BACKLOG, ws.backlog)

        for run_ in ws.runs():
            d = derive_run(ws, run_, gs, errs)
            upd = {"current_phase": d["phase"], "current_step": d["current_step"], "status": d["status"],
                   "next_step": d["next_step"], "last_completed_step": d["last_completed_step"],
                   "blocked_reason": d["blocked_reason"] if d["status"] == "BLOCKED" else None}
            diff = {k: v for k, v in upd.items() if run_.get(k) != v}
            if diff:
                run_.update(diff)
                run_["updated_at"] = store.now()
                changed["state"] = True
        if changed["state"]:
            ws.state["updated_at"] = store.now()
            store.save_json(paths.STATE, ws.state)

        changed["graph"] = graph.save(ws)
        changed["views"] = len(views.write_all(ws))
        changed["errors"] = sum(1 for i in issues if i.level == "ERROR")
        changed["warnings"] = sum(1 for i in issues if i.level == "WARN")
        return changed
