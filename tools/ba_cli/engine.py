"""Derives the next step for every run and use case from artifacts + gates.

Position is *computed*, not remembered: resuming after a crash or a new session
always lands on the right step (master spec §4, §40).
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from . import coding, gates, prereview, schema
from .ids import as_list
from .workspace import Workspace

PHASE_ORDER = ("SPECIFICATION", "TECHNICAL_REVIEW", "TEST_DESIGN", "CODING", "QA", "CODE_REVIEW",
               "CRITICAL_FLOW_TEST", "USER_GUIDE")
HUMAN_CLASSES = ("SPECIFICATION_GAP", "ENVIRONMENT_ISSUE", "UNRESOLVED")


class GateCache:
    def __init__(self, ws: Workspace):
        self.ws, self._c = ws, {}

    def __call__(self, gid: str, subject: str) -> dict:
        if (gid, subject) not in self._c:
            self._c[(gid, subject)] = gates.status(self.ws, gid, subject)
        return self._c[(gid, subject)]


# ------------------------------------------------------------------ per use case

def _step_group(steps: List[dict], i: int) -> List[dict]:
    """Consecutive steps for the same agent, ending at the first gated step."""
    group = [steps[i]]
    for st in steps[i + 1:]:
        if group[-1].get("gate") or not st.get("artifact_type") or st.get("agent") != steps[i].get("agent"):
            break
        group.append(st)
    return group


def _action(ws, uc, st, action, group, **kw) -> dict:
    d = {"uc": uc, "name": ws.label(uc), "state": "ACTION", "action": action,
         "step": st["step"], "step_name": st["name"], "phase": st.get("phase"),
         "steps": [s["step"] for s in group],
         "agent": st.get("agent"), "skills": sum((s.get("skills", []) for s in group), []),
         "outputs": [ws.doc_rel(s["artifact_type"], uc) for s in group if s.get("artifact_type")], "gate": None}
    pre = next((s["pre_command"] for s in group if s.get("pre_command")), None)
    if pre:
        d["pre_command"] = pre.format(UC=uc)
    d.update(kw)
    return d


def gate_required(ws: Workspace, uc: str, gid: str) -> bool:
    return schema.gate_required(gid, ws.item(uc))


def qa_passed(ws: Workspace, uc: str) -> bool:
    """Automated QA is complete: results exist, are current, PASSED, and no defect is still open."""
    doc = ws.docs.get(ws.doc_rel("test-results", uc))
    if doc is None or ws.stale_reasons(doc) or doc.fm.get("outcome") != "PASSED":
        return False
    if _retest_requested(doc):
        return False
    return not any(d.get("status") in ("OPEN", "UNRESOLVED") for d in ws.defects(uc))


def _retest_requested(doc) -> bool:
    req = doc.fm.get("retest_requested_at")
    return bool(req) and str(req) > str(doc.fm.get("executed_at") or "")


def _qa_loop(ws: Workspace, uc: str, st: dict, doc, steps: List[dict], i: int) -> Optional[dict]:
    """Steps 8.3–8.4: route each failure by its classification. None means QA passed."""
    if _retest_requested(doc):
        return _action(ws, uc, st, "REGENERATE", [st], reason="retest requested (tools/ba qa retest)")
    eng = schema.engine()
    max_attempts = int(eng.get("max_fix_attempts", 3))
    defects = ws.defects(uc)
    open_ = [d for d in defects if d.get("status") == "OPEN"]
    outcome = doc.fm.get("outcome")
    if outcome == "BLOCKED":
        return {"uc": uc, "name": ws.label(uc), "state": "NEEDS_HUMAN", "step": "8.2", "phase": "QA",
                "reason": "tests could not run: " + str(doc.fm.get("blocked_reason") or "see test results")
                          + f" — fix the cause, then ask for a retest (tools/ba qa retest {uc})"}
    unresolved = [d for d in defects if d.get("status") == "UNRESOLVED"]
    if outcome == "PASSED" and not open_ and not unresolved:
        return None
    if not open_ and not unresolved:
        return _action(ws, uc, st, "FIX", [st],
                       reason=f"outcome is {outcome!r} but qa/defects/{uc}.md lists no OPEN defect — "
                              f"record every failure as a defect (or set outcome PASSED)")
    tests = [d for d in open_ if d.get("classification") == "TEST_ISSUE"]
    if tests:
        tc_step = next(s for s in steps if s.get("artifact_type") == "test-cases")
        return _action(ws, uc, tc_step, "FIX_TESTS", _step_group(steps, steps.index(tc_step)),
                       defects=[d["id"] for d in tests],
                       reason="test issues: " + ", ".join(d["id"] for d in tests))
    code = [d for d in open_ if d.get("classification") == "CODE_DEFECT"
            and int(d.get("fix_attempts") or 0) < max_attempts]
    if code:
        impl = next(s for s in steps if s.get("artifact_type") == "implementation")
        return {"uc": uc, "name": ws.label(uc), "state": "ACTION", "action": "FIX_DEFECT", "step": "8.4",
                "step_name": "Automated Fix Loop", "phase": "QA", "steps": ["8.4"],
                "agent": impl["agent"], "skills": ["fix-defects"],
                "outputs": [ws.doc_rel("implementation", uc), ws.doc_rel("defects", uc)], "gate": None,
                "pre_command": impl["pre_command"].format(UC=uc), "defects": [d["id"] for d in code],
                "reason": "code defects to fix: " + ", ".join(
                    f"{d['id']} (attempt {int(d.get('fix_attempts') or 0) + 1} of {max_attempts})" for d in code)}
    human = unresolved + [d for d in open_ if d not in tests and d not in code]
    why = []
    for d in human:
        cls = d.get("classification")
        if d.get("status") == "UNRESOLVED" or (cls == "CODE_DEFECT"):
            why.append(f"{d['id']} UNRESOLVED after {d.get('fix_attempts', 0)} fix attempts")
        else:
            why.append(f"{d['id']} {cls}")
    return {"uc": uc, "name": ws.label(uc), "state": "NEEDS_HUMAN", "step": "8.3", "phase": "QA",
            "defects": [d["id"] for d in human],
            "reason": "defects need a human decision: " + "; ".join(why)}


def _gate_request_or_review(ws, uc, st, gid, g, steps, base) -> dict:
    """The gate is due for a request: first the AI pre-review (D-40), then REQUEST_GATE."""
    pr = prereview.state(ws, gid, uc, g)
    if pr["status"] == "NEEDED":
        return {**base, "state": "ACTION", "action": "PRE_REVIEW", "step": gid, "step_name": f"AI pre-review of {gid}",
                "gate": gid, "phase": st.get("phase"), "steps": [], "agent": "review-agent",
                "skills": ["pre-review-gate"], "outputs": [], "round": pr["round"],
                "brief_command": f"tools/ba prereview brief {gid} {uc}",
                "reason": f"round {pr['round']} of {prereview.max_rounds()} before the human review"}
    if pr["status"] == "FINDINGS":
        owners = prereview.owner_steps(ws, gid, uc, pr["findings"], steps)
        rev = (schema.gate(gid) or {}).get("revise_agent")
        if rev and any(o["agent"] == rev for o in owners):
            owners = [o for o in owners if o["agent"] == rev]
        first = owners[0] if owners else next(x for x in steps if x.get("artifact_type"))
        group = [o for o in owners if o["agent"] == first["agent"]] or [first]
        return _action(ws, uc, first, "REVISE", group, gate=gid, comments=prereview.format_findings(pr["findings"]),
                       comments_gate=f"{gid} AI pre-review", reviewer="review-agent", pre_review=True,
                       resolve_command=f"tools/ba prereview resolve {gid} {uc} --note '<why the findings stay>'")
    out = {**base, "state": "ACTION", "action": "REQUEST_GATE", "step": gid, "gate": gid,
           "phase": st.get("phase"), "agent": None, "executor": "orchestrator", "reason": g["status"]}
    if pr.get("carried"):
        out["pre_review_findings"] = prereview.format_findings(pr["carried"])
    return out


def _setup_action(ws, uc, st, base) -> Optional[dict]:
    """D-39: the product repositories must exist (and be ACTIVE) before tests or code are written."""
    ok, why = coding.repositories_ready(ws)
    if ok:
        return None
    impl = next(s for s in schema.engine_steps() if s.get("artifact_type") == "implementation")
    return {**base, "state": "ACTION", "action": "SETUP_REPOSITORIES", "step": "7.0",
            "step_name": "Repository Setup", "phase": "CODING", "steps": ["7.0"], "agent": impl["agent"],
            "skills": ["set-up-repositories"], "outputs": [], "gate": None, "shared": True,
            "pre_command": impl["pre_command"].format(UC=uc), "reason": "; ".join(why)}


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

    steps = schema.uc_steps()

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
        if st.get("needs_repositories"):
            setup = _setup_action(ws, uc, st, base)
            if setup:
                return setup
        if st.get("artifact_type"):
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
            if st.get("qa_loop"):
                r = _qa_loop(ws, uc, st, doc, steps, i)
                if r:
                    return r
        gid = st.get("gate")
        if not gid or not gate_required(ws, uc, gid):
            continue
        g = gs(gid, uc)
        s = g["status"]
        if s == "APPROVED":
            continue
        if s == "WAITING":
            return {**base, "state": "WAITING", "step": gid, "gate": gid, "phase": st.get("phase"),
                    "requested_at": g["request"]["requested_at"]}
        if s == "CHANGES_REQUESTED":
            rels = gates.artifact_rels(gid, uc)
            covered = [x for x in steps if x.get("artifact_type")
                       and any(ws.doc_rel(x["artifact_type"], uc) == r
                               or (r.endswith("/") and ws.doc_rel(x["artifact_type"], uc).startswith(r))
                               for r in rels)]
            rev = (schema.gate(gid) or {}).get("revise_agent")
            if rev and any(x["agent"] == rev for x in covered):
                covered = [x for x in covered if x["agent"] == rev]
            agents = sorted({x["agent"] for x in covered})
            return _action(ws, uc, covered[0], "REVISE", covered, gate=gid, comments=g["comments"],
                           comments_gate=gid, agent=agents[0] if len(agents) == 1 else None,
                           agents=agents, reviewer=g["decision"].get("reviewer"))
        if s == "BLOCKED":
            return {**base, "state": "BLOCKED", "step": gid, "gate": gid, "phase": st.get("phase"),
                    "reason": f"{gid} decision BLOCKED: {g['comments']}"}
        return _gate_request_or_review(ws, uc, st, gid, g, steps, base)
    return {**base, "state": "DONE", "step": "DELIVERED", "phase": "DONE"}


# ------------------------------------------------------------------ run-level steps

def _next_gate(route: List[dict], idx: int) -> Optional[str]:
    """The first run-level gate after route[idx], if one comes before the use-case engine."""
    for item in route[idx + 1:]:
        if item["kind"] == "gate":
            return item["id"]
        if item["kind"] == "use_case_engine":
            return None
    return None


def run_step_outputs(ws: Workspace, sid: str) -> List[dict]:
    """[{path, built_from, app?}] the step must produce right now."""
    sdef = schema.run_step(sid) or {}
    outs = [dict(o) for o in sdef.get("outputs") or []]
    pa = sdef.get("per_application")
    if pa:
        for app in ws.ia_applications():
            outs.append({"path": pa["path"].format(APP=app["id"]), "built_from": pa.get("built_from", []),
                         "app": app["id"]})
    return outs


def blocking_questions(ws: Workspace) -> List[dict]:
    return [q for q in ws.items_in("open-questions") if q.get("status") == "OPEN" and q.get("blocking") is True]


def unplanned_use_cases(ws: Workspace) -> List[str]:
    return [u["id"] for u in ws.items_in("use-cases") if u["id"] not in ws.backlog_ucs]


def derive_run_step(ws: Workspace, sid: str, errs: Dict[str, list]) -> Optional[dict]:
    """None when the step is complete; otherwise a dict with status / run_action for the run."""
    sdef = schema.run_step(sid)
    if not sdef:
        return {"status": "BLOCKED", "blocked_reason": f"run step {sid} is not defined in workflow.yaml"}
    outs = run_step_outputs(ws, sid)
    started = any(o["path"] in ws.docs for o in outs)
    for d in sdef.get("requires_input") or []:
        if ws.hash_rel(d) is None:
            return {"status": "BLOCKED" if started else "NOT_STARTED",
                    "next_step": f"add stakeholder material to ba-ai/{d}, then /ba-next",
                    "blocked_reason": f"{sid} needs input: ba-ai/{d} is empty"}
    reasons: Dict[str, List[str]] = {"GENERATE": [], "REGENERATE": [], "FIX": []}
    for o in outs:
        doc = ws.docs.get(o["path"])
        if doc is None:
            reasons["GENERATE"].append(f"ba-ai/{o['path']} is missing")
            continue
        stale = ws.stale_reasons(doc)
        if stale:
            reasons["REGENERATE"] += [f"ba-ai/{o['path']}: {r}" for r in stale]
        elif o.get("built_from") and not doc.fm.get("built_from"):
            reasons["FIX"].append(f"ba-ai/{o['path']} is not stamped (tools/ba stamp)")
        if errs.get(o["path"]):
            reasons["FIX"] += [f"ba-ai/{o['path']}: {m}" for m in errs[o["path"]]]
    for cname in sdef.get("catalogs") or []:
        cpath = schema.catalogs()[cname]["path"]
        if not ws.items_in(cname):
            reasons["GENERATE"].append(f"catalog ba-ai/{cpath} has no items")
        if errs.get(cpath):
            reasons["FIX"] += [f"ba-ai/{cpath}: {m}" for m in errs[cpath]]
    if sdef.get("backlog"):
        if not ws.epics:
            reasons["GENERATE"].append("planning/backlog.yaml has no epics")
        else:
            missing = unplanned_use_cases(ws)
            if missing:
                reasons["REGENERATE"].append("use cases not planned yet: " + ", ".join(missing))
        if errs.get("planning/backlog.yaml"):
            reasons["FIX"] += errs["planning/backlog.yaml"]
    action = next((a for a in ("GENERATE", "REGENERATE", "FIX") if reasons[a]), None)
    if action:
        all_reasons = reasons["GENERATE"] + reasons["REGENERATE"] + reasons["FIX"]
        return {"status": "IN_PROGRESS", "next_step": f"{sid} {action}",
                "run_action": {"action": action, "step": sid, "step_name": sdef["name"],
                               "phase": sdef.get("phase"), "agent": sdef["agent"],
                               "skills": sdef.get("skills", []), "outputs": [o["path"] for o in outs],
                               "context_command": f"tools/ba context {sid}",
                               "reason": "; ".join(all_reasons)}}
    if sdef.get("stakeholder_wait"):
        qs = blocking_questions(ws)
        if qs:
            return {"status": "WAITING_FOR_HUMAN",
                    "next_step": "stakeholder input: answer " + ", ".join(q["id"] for q in qs)
                                 + " — add meeting notes to ba-ai/requirements/meetings/, then /ba-next",
                    "run_action": {"action": "WAIT_FOR_STAKEHOLDERS", "step": sid,
                                   "questions": [{k: q.get(k) for k in ("id", "question", "target_stakeholder",
                                                                         "priority", "reason")} for q in qs]}}
    return None


def derive_run(ws: Workspace, run: dict, gs: Callable, errs: Dict[str, list]) -> dict:
    mode = schema.workflow()["modes"][run["workflow_type"]]
    route = mode["route"]
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

    for idx, item in enumerate(route):
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
                        blocked_reason=f"{iid} has no engine yet and its outputs are missing: "
                                       + ", ".join(missing))
        if kind == "run_step":
            nxt = _next_gate(route, idx)
            if nxt and gs(nxt, run["run_id"])["status"] == "APPROVED":
                last = iid           # the gate after it approved what it produced
                continue
            r = derive_run_step(ws, iid, errs)
            if r is None:
                last = iid
                continue
            return stop(phase=iid, current_step=iid, status=r["status"], next_step=r.get("next_step"),
                        blocked_reason=r.get("blocked_reason"), run_action=r.get("run_action"))
        if kind == "gate":
            g = schema.gate(iid)
            if not g.get("implemented"):
                return stop(phase=iid, current_step=iid, status="BLOCKED", next_step=iid,
                            blocked_reason=f"next: {iid} {g['name']} — not built yet")
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
                                        "agent": g.get("revise_agent"),
                                        "step": next((r["id"] for r in reversed(route[:idx])
                                                      if r["kind"] == "run_step"), None),
                                        "comments": st["comments"],
                                        "reviewer": (st.get("decision") or {}).get("reviewer"),
                                        "artifacts": gates.artifact_rels(iid, run["run_id"])})
            if s == "BLOCKED":
                return stop(phase=iid, current_step=iid, status="BLOCKED", next_step=iid,
                            blocked_reason=f"{iid} decision BLOCKED: {st['comments']}")
            producing = next((r["id"] for r in reversed(route[:idx]) if r["kind"] == "run_step"), None)
            absent = [r for r in gates.artifact_rels(iid, run["run_id"]) if ws.hash_rel(r) is None]
            if absent and producing:
                sdef = schema.run_step(producing) or {}
                return stop(phase=producing, current_step=producing, status="IN_PROGRESS",
                            next_step=f"{producing} FIX", run_action={
                                "action": "FIX", "step": producing, "step_name": sdef.get("name"),
                                "phase": sdef.get("phase"), "agent": sdef.get("agent"),
                                "skills": sdef.get("skills", []), "outputs": absent,
                                "context_command": f"tools/ba context {producing}",
                                "reason": f"{iid} reviews " + ", ".join(f"ba-ai/{r}" for r in absent)
                                          + ", which does not exist — create it (an empty catalog is fine when "
                                            "there are no items: `tools/ba catalog init <catalog>`)"})
            pr = prereview.state(ws, iid, run["run_id"], st)
            if pr["status"] == "NEEDED":
                return stop(phase=iid, current_step=iid, status="IN_PROGRESS",
                            next_step=f"AI pre-review of {iid} (round {pr['round']})",
                            run_action={"action": "PRE_REVIEW", "gate": iid, "subject": run["run_id"],
                                        "agent": "review-agent", "round": pr["round"],
                                        "brief_command": f"tools/ba prereview brief {iid} {run['run_id']}"})
            if pr["status"] == "FINDINGS":
                return stop(phase=iid, current_step=iid, status="IN_PROGRESS",
                            next_step=f"address AI pre-review findings on {iid}",
                            run_action={"action": "REVISE", "gate": iid, "subject": run["run_id"],
                                        "agent": g.get("revise_agent"), "step": producing, "pre_review": True,
                                        "comments": prereview.format_findings(pr["findings"]),
                                        "reviewer": "review-agent",
                                        "resolve_command": f"tools/ba prereview resolve {iid} {run['run_id']} "
                                                           f"--note '<why the findings stay>'",
                                        "artifacts": gates.artifact_rels(iid, run["run_id"])})
            ra = {"action": "REQUEST_GATE", "gate": iid, "subject": run["run_id"], "reason": s}
            if pr.get("carried"):
                ra["pre_review_findings"] = prereview.format_findings(pr["carried"])
            return stop(phase=iid, current_step=iid, status="IN_PROGRESS",
                        next_step=f"request {iid} {g['name']}", run_action=ra)
        if kind == "use_case_engine":
            results = {uc: derive_uc(ws, uc, run, gs, errs) for uc in ws.run_use_cases(run)}
            if results and all(r["state"] == "DONE" for r in results.values()):
                last = iid
                res["use_cases"] = results
                continue
            actions = [r for r in results.values() if r["state"] == "ACTION"]
            waiting = [r for r in results.values() if r["state"] in ("WAITING", "NEEDS_HUMAN")]
            if actions:
                status, nxt = "IN_PROGRESS", "; ".join(f"{r['uc']} {r['step']} {r['action']}" for r in actions)
            elif waiting:
                status, nxt = "WAITING_FOR_HUMAN", "human: " + ", ".join(
                    f"{r['uc']} {r.get('gate') or 'defects'}" for r in waiting)
                if all(r["state"] == "WAITING" for r in waiting):
                    nxt = "human review: " + ", ".join(f"{r['uc']} {r['gate']}" for r in waiting)
            else:
                status, nxt = "BLOCKED", None
            blocked = "; ".join(f"{r['uc']}: {r['reason']}" for r in results.values()
                                if r["state"] in ("BLOCKED", "NOT_READY"))
            phases = [r.get("phase") for r in results.values() if r.get("phase") in PHASE_ORDER]
            phase = min(phases, key=PHASE_ORDER.index) if phases else "SPECIFICATION"
            return stop(phase=phase, current_step="PER_USE_CASE", status=status, next_step=nxt,
                        blocked_reason=blocked or None, use_cases=results)
    return stop(phase="COMPLETED", current_step=None, status="COMPLETED")
