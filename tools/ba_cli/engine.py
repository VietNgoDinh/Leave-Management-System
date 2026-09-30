"""Derives the next step for every run and use case from artifacts + gates.

Position is *computed*, not remembered: resuming after a crash or a new session
always lands on the right step (master spec §4, §40).
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from . import gates, schema
from .ids import as_list
from .workspace import Workspace


class GateCache:
    def __init__(self, ws: Workspace):
        self.ws, self._c = ws, {}

    def __call__(self, gid: str, subject: str) -> dict:
        if (gid, subject) not in self._c:
            self._c[(gid, subject)] = gates.status(self.ws, gid, subject)
        return self._c[(gid, subject)]


def _step_group(steps: List[dict], i: int) -> List[dict]:
    """Consecutive steps for the same agent, ending at the first gated step."""
    group = [steps[i]]
    for st in steps[i + 1:]:
        if group[-1].get("gate") or st.get("agent") != steps[i].get("agent"):
            break
        group.append(st)
    return group


def _action(ws, uc, st, action, group, **kw) -> dict:
    d = {"uc": uc, "name": ws.label(uc), "state": "ACTION", "action": action,
         "step": st["step"], "step_name": st["name"], "steps": [s["step"] for s in group],
         "agent": st.get("agent"), "skills": sum((s.get("skills", []) for s in group), []),
         "outputs": [ws.doc_rel(s["artifact_type"], uc) for s in group], "gate": None}
    d.update(kw)
    return d


def derive_uc(ws: Workspace, uc: str, run: Optional[dict], gs: Callable, errs: Dict[str, list]) -> dict:
    eng = schema.engine()
    base = {"uc": uc, "name": ws.label(uc)}
    bl = ws.backlog_ucs.get(uc)
    if not bl:
        return {**base, "state": "BLOCKED", "step": None, "reason": "not in planning/backlog.yaml"}
    item = bl["item"]
    if item.get("status") == "BACKLOG":
        return {**base, "state": "NOT_READY", "step": None,
                "reason": "backlog status is BACKLOG — the BA sets it to READY when it can be specified"}
    if item.get("status") == "BLOCKED":
        return {**base, "state": "BLOCKED", "step": None,
                "reason": item.get("blocked_reason") or "marked BLOCKED in the backlog"}
    for gid in eng["requires_gates"]:
        s = gs(gid, run["run_id"])["status"] if run else "NOT_REQUESTED"
        if s != "APPROVED":
            return {**base, "state": "BLOCKED", "step": None, "waiting_on": gid,
                    "reason": f"needs {gid} approved for {run['run_id'] if run else 'the run'} (now {s})"}
    for dep in as_list(item.get("dependencies")):
        s = gs(eng["dependency_gate"], dep)["status"]
        if s != "APPROVED":
            return {**base, "state": "BLOCKED", "step": None, "waiting_on": dep,
                    "reason": f"depends on {dep} ({eng['dependency_gate']} is {s})"}

    steps = schema.engine_steps()

    def pending_comments(i: int) -> dict:
        """Reviewer comments still to address on the gate that covers step i."""
        gate_step = next((s for s in steps[i:] if s.get("gate")), None)
        if not gate_step:
            return {}
        g = gs(gate_step["gate"], uc)
        dec = g.get("decision")
        if dec and dec.get("decision") == "CHANGES_REQUESTED":
            return {"comments": dec.get("comments"), "comments_gate": gate_step["gate"],
                    "reviewer": dec.get("reviewer")}
        return {}

    for i, st in enumerate(steps):
        rel = ws.doc_rel(st["artifact_type"], uc)
        doc = ws.docs.get(rel)
        group = _step_group(steps, i)
        if doc is None:
            return _action(ws, uc, st, "GENERATE", group, **pending_comments(i))
        stale = ws.stale_reasons(doc)
        if stale:
            return _action(ws, uc, st, "REGENERATE", group, reason="; ".join(stale), **pending_comments(i))
        if errs.get(rel):
            return _action(ws, uc, st, "FIX", [st], reason=errs[rel], **pending_comments(i))
        gid = st.get("gate")
        if not gid:
            continue
        g = gs(gid, uc)
        s = g["status"]
        if s == "APPROVED":
            continue
        if s == "WAITING":
            return {**base, "state": "WAITING", "step": gid, "gate": gid,
                    "requested_at": g["request"]["requested_at"]}
        if s == "CHANGES_REQUESTED":
            rels = gates.artifact_rels(gid, uc)
            covered = [x for x in steps
                       if any(ws.doc_rel(x["artifact_type"], uc) == r
                              or (r.endswith("/") and ws.doc_rel(x["artifact_type"], uc).startswith(r))
                              for r in rels)]
            agents = sorted({x["agent"] for x in covered})
            return _action(ws, uc, covered[0], "REVISE", covered, gate=gid, comments=g["comments"],
                           comments_gate=gid, agent=agents[0] if len(agents) == 1 else None,
                           agents=agents, reviewer=g["decision"].get("reviewer"))
        if s == "BLOCKED":
            return {**base, "state": "BLOCKED", "step": gid, "gate": gid,
                    "reason": f"{gid} decision BLOCKED: {g['comments']}"}
        return {**base, "state": "ACTION", "action": "REQUEST_GATE", "step": gid, "gate": gid,
                "agent": None, "executor": "orchestrator", "reason": s}
    return {**base, "state": "DONE", "step": "SPEC_APPROVED"}


def derive_run(ws: Workspace, run: dict, gs: Callable, errs: Dict[str, list]) -> dict:
    mode = schema.workflow()["modes"][run["workflow_type"]]
    res = {"run_id": run["run_id"], "workflow_type": run["workflow_type"], "phase": None,
           "status": None, "current_step": None, "next_step": None, "blocked_reason": None,
           "last_completed_step": None, "run_action": None, "use_cases": {}}
    last = None

    def stop(**kw):
        res.update(kw)
        res["last_completed_step"] = last
        if run.get("manual_block"):
            res["status"] = "BLOCKED"
            res["blocked_reason"] = run.get("blocked_reason") or "blocked manually"
        return res

    for item in mode["route"]:
        iid, kind = item["id"], item["kind"]
        if kind == "step":
            outs = item.get("outputs", [])
            if all(ws.hash_rel(o) is not None for o in outs):
                last = iid
                continue
            if item.get("optional"):
                continue
            missing = [o for o in outs if ws.hash_rel(o) is None]
            return stop(phase=iid, current_step=iid, status="BLOCKED", next_step=iid,
                        blocked_reason=f"{iid} has no engine in milestone 1 and its outputs are missing: "
                                       + ", ".join(missing))
        if kind == "gate":
            g = schema.gate(iid)
            if not g.get("implemented"):
                return stop(phase=iid, current_step=iid, status="BLOCKED", next_step=iid,
                            blocked_reason=f"next: {iid} {g['name']} — not available in milestone 1")
            st = gs(iid, run["run_id"])
            s = st["status"]
            if s == "APPROVED":
                last = iid
                continue
            if s == "WAITING":
                return stop(phase=iid, current_step=iid, status="WAITING_FOR_HUMAN",
                            next_step=f"human review of {iid} {g['name']}")
            if s == "CHANGES_REQUESTED":
                return stop(phase=iid, current_step=iid, status="CHANGES_REQUESTED",
                            next_step=f"revise {iid} artifacts per reviewer comments",
                            run_action={"action": "REVISE", "gate": iid, "subject": run["run_id"],
                                        "comments": st["comments"],
                                        "artifacts": gates.artifact_rels(iid, run["run_id"])})
            if s == "BLOCKED":
                return stop(phase=iid, current_step=iid, status="BLOCKED", next_step=iid,
                            blocked_reason=f"{iid} decision BLOCKED: {st['comments']}")
            return stop(phase=iid, current_step=iid, status="IN_PROGRESS",
                        next_step=f"request {iid} {g['name']}",
                        run_action={"action": "REQUEST_GATE", "gate": iid, "subject": run["run_id"],
                                    "reason": s})
        if kind == "use_case_engine":
            results = {uc: derive_uc(ws, uc, run, gs, errs) for uc in ws.run_use_cases(run)}
            if results and all(r["state"] == "DONE" for r in results.values()):
                last = iid
                continue
            actions = [r for r in results.values() if r["state"] == "ACTION"]
            waiting = [r for r in results.values() if r["state"] == "WAITING"]
            if actions:
                status, nxt = "IN_PROGRESS", "; ".join(f"{r['uc']} {r['step']} {r['action']}" for r in actions)
            elif waiting:
                status, nxt = "WAITING_FOR_HUMAN", "human review: " + ", ".join(f"{r['uc']} {r['gate']}" for r in waiting)
            else:
                status, nxt = "BLOCKED", None
            blocked = "; ".join(f"{r['uc']}: {r['reason']}" for r in results.values()
                                if r["state"] in ("BLOCKED", "NOT_READY"))
            return stop(phase=iid, current_step="PER_USE_CASE", status=status, next_step=nxt,
                        blocked_reason=blocked or None, use_cases=results)
    return stop(phase="COMPLETED", current_step=None, status="COMPLETED")
