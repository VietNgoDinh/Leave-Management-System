"""Step 5.1 — build the minimal context package for one use case (master spec §35)."""
from __future__ import annotations

from typing import List, Tuple

from . import coding, paths, schema, store
from .engine import (GateCache, blocking_questions, gate_required, run_step_outputs,
                     unplanned_use_cases)
from .ids import as_list, normalize_id
from .store import BAError
from .workspace import Workspace

DESIGN_DOCS = (
    ("product_overview", "overview/product-overview.md", True),
    ("design_system", "ui/design-system.md", True),
    ("architecture", "technical/architecture/architecture.md", True),
    ("frontend_rules", "technical/coding-rules/frontend.md", False),
    ("backend_rules", "technical/coding-rules/backend.md", False),
    ("security_rules", "technical/security/security-rules.md", False),
)


def _unique(seq):
    return list(dict.fromkeys(x for x in seq if x))


def build(uc_arg: str) -> Tuple[str, List[str]]:
    uc = normalize_id(uc_arg)
    ws = Workspace()
    if ws.catalog_of(uc) != "use-cases":
        raise BAError(f"{uc} is not in overview/use-cases.yaml")
    gs = GateCache(ws)
    item = ws.item(uc)
    missing: List[str] = []
    run = ws.active_run()

    def get(iid, what):
        rec = ws.item(iid) if iid else None
        if rec is None:
            missing.append(f"{what} {iid or '(not set)'} referenced by {uc} was not found")
        return rec

    bl = ws.backlog_ucs.get(uc)
    if not bl:
        missing.append(f"{uc} is not in planning/backlog.yaml")
    for gid in schema.engine()["requires_gates"]:
        s = gs(gid, run["run_id"])["status"] if run else "missing (no active run)"
        if s != "APPROVED":
            missing.append(f"{gid} is {s}; it must be APPROVED before specifying use cases")

    actor = get(item.get("actor"), "actor")
    app = get(item.get("application"), "application")
    bp = get(item.get("business_process"), "business process")
    step = next((st for st in as_list((bp or {}).get("steps")) if uc in as_list(st.get("use_cases"))), None)

    rule_ids = _unique(as_list(item.get("business_rules")) +
                       [r["id"] for r in ws.items_in("business-rules") if uc in as_list(r.get("related_use_cases"))])
    rules = [r for r in (get(i, "business rule") for i in rule_ids) if r]
    ent_ids = _unique(as_list(item.get("entities_read")) + as_list(item.get("entities_written")))
    entities = [e for e in (get(i, "entity") for i in ent_ids) if e]
    related_ent_ids = _unique(e for r in rules for e in as_list(r.get("related_entities")) if e not in ent_ids)
    reqs = [r for r in (get(i, "requirement") for i in as_list(item.get("requirements"))) if r]
    all_ents = set(ent_ids) | set(related_ent_ids)

    related = []
    for other in ws.items_in("use-cases"):
        if other["id"] != uc and other.get("business_process") == item.get("business_process"):
            related.append({"id": other["id"], "name": other.get("name"), "relation": "same business process"})
    if bl:
        for dep in as_list(bl["item"].get("dependencies")):
            related.append({"id": dep, "name": ws.label(dep), "relation": f"{uc} depends on it"})
    for other_uc, rec in ws.backlog_ucs.items():
        if uc in as_list(rec["item"].get("dependencies")):
            related.append({"id": other_uc, "name": ws.label(other_uc), "relation": f"depends on {uc}"})

    screens = ws.items_in("screens")
    screens_uc = [s for s in screens if uc in as_list(s.get("use_cases"))]
    screens_app = [{"id": s["id"], "name": s.get("name"), "route": s.get("route")} for s in screens
                   if s.get("application") == item.get("application") and s not in screens_uc]
    apis = [a for a in ws.items_in("apis")
            if uc in as_list(a.get("introduced_by"))
            or all_ents & set(as_list(a.get("entities_read")) + as_list(a.get("entities_written")))]
    integrations = [i for i in ws.items_in("integrations") if all_ents & set(as_list(i.get("entities")))]
    topics = {uc} | set(rule_ids) | all_ents
    questions = [q for q in ws.items_in("open-questions")
                 if q.get("status") != "CLOSED" and topics & set(as_list(q.get("related")))]
    assumptions = [a for a in ws.items_in("assumptions")
                   if a.get("status") != "REJECTED" and topics & set(as_list(a.get("related")))]

    design = {}
    for key, rel, required in DESIGN_DOCS:
        if (paths.BA / rel).exists():
            design[key] = paths.show(rel)
        elif required:
            missing.append(f"ba-ai/{rel} is missing")

    artifacts = {}
    for st in schema.engine_steps():
        rel = ws.doc_rel(st["artifact_type"], uc)
        doc = ws.docs.get(rel)
        artifacts[st["step"]] = {"artifact_type": st["artifact_type"], "path": paths.show(rel),
                                 "exists": doc is not None,
                                 "status": doc.fm.get("status") if doc else None}
    gate_info = {}
    for gid, g in schema.workflow()["gates"].items():
        if g.get("subject") == "USE_CASE" and g.get("implemented"):
            st = gs(gid, uc)
            gate_info[gid] = {"status": st["status"]}
            if not gate_required(ws, uc, gid):
                gate_info[gid]["required"] = False
            if st["comments"]:
                gate_info[gid]["latest_comments"] = st["comments"]
    app_id = item.get("application")
    ia_rel = f"planning/information-architecture/{app_id}.md"
    if (paths.BA / ia_rel).exists():
        design["information_architecture"] = paths.show(ia_rel)
    delivery = {
        "repositories": [{"id": i, "name": n, "path": str(pth), "exists": pth.exists(),
                          "status": (ws.item(i) or {}).get("status"),
                          "worktree": str(coding.worktree_path(pth, uc)),
                          "worktree_exists": coding.worktree_path(pth, uc).exists()}
                         for i, n, pth in coding.repositories(ws)],
        "coding_authorized": uc in coding.authorized(ws),
        "branch_convention": f"ba/{uc}-<slug> (D-25), checked out in the use case's worktree (D-39)",
        "risk_level": item.get("risk_level"),
        "risk_flags": as_list(item.get("risk_flags")),
        "critical_flow_test_required": gate_required(ws, uc, "GATE-07"),
        "max_fix_attempts": schema.engine().get("max_fix_attempts", 3),
        "defects": ws.defects(uc),
        "test_cases": sorted(tc for tc, t in ws.test_cases.items() if t["uc"] == uc),
    }

    epic = ws.epics.get(bl["epic"]) if bl else None
    pkg = {
        "task": f"Specify {uc} — {item.get('name')}",
        "generated_at": store.now(),
        "use_case": item,
        "epic": {"id": epic.get("epic_id"), "name": epic.get("name")} if epic else None,
        "backlog": {k: bl["item"].get(k) for k in ("priority", "status", "dependencies", "current_step")} if bl else None,
        "actor": actor,
        "application": app,
        "business_process": {k: bp.get(k) for k in ("id", "name", "objective", "trigger")} if bp else None,
        "process_step": step,
        "requirements": reqs,
        "business_rules": rules,
        "entities": entities,
        "related_entities": [{"id": e, "name": ws.label(e)} for e in related_ent_ids],
        "related_use_cases": related,
        "existing_screens": screens_uc,
        "other_screens_in_application": screens_app,
        "existing_apis": apis,
        "integrations": integrations,
        "open_questions": questions,
        "assumptions": assumptions,
        "design_constraints": design,
        "artifacts": artifacts,
        "gates": gate_info,
        "delivery": delivery,
        "missing": missing,
    }
    out = paths.CONTEXT_DIR / f"{uc}.yaml"
    store.save_yaml(out, pkg)
    return paths.show(paths.rel(out)), missing


# ------------------------------------------------------------------ run-level steps

def _listing(rel: str) -> List[str]:
    p = paths.BA / rel.rstrip("/")
    if p.is_dir():
        return sorted(paths.show(paths.rel(f)) for f in p.rglob("*")
                      if f.is_file() and not any(x.startswith(".") for x in f.relative_to(p).parts))
    return [paths.show(rel)] if p.exists() else []


def _items(ws: Workspace, cname: str, fields) -> List[dict]:
    return [{k: i.get(k) for k in ("id",) + tuple(fields) if i.get(k) is not None} for i in ws.items_in(cname)]


def build_run(step_arg: str) -> Tuple[str, List[str]]:
    """Context package for a run-level step (ELICITATION, OVERVIEW, TECH_BASELINE, PLANNING, …)."""
    sid = step_arg.strip().upper()
    sdef = schema.run_step(sid)
    if not sdef:
        raise BAError(f"{step_arg} is neither a use case nor a run step ({', '.join(schema.run_steps())})")
    ws = Workspace()
    gs = GateCache(ws)
    run = ws.active_run()
    missing: List[str] = []
    if not run:
        missing.append("no active run in workflow/state.json")
    inputs: List[str] = []
    for d in sdef.get("requires_input") or []:
        files = _listing(d)
        if not files:
            missing.append(f"ba-ai/{d} is empty — the BA must add stakeholder material first")
        inputs += files
    outputs = []
    for o in run_step_outputs(ws, sid):
        for b in o.get("built_from", []):
            rel, optional = schema.optional_input(b)
            files = _listing(rel)
            if not files and not optional and rel not in (sdef.get("requires_input") or []) \
                    and not any(rel == x["path"] for x in run_step_outputs(ws, sid)):
                missing.append(f"input ba-ai/{rel} of ba-ai/{o['path']} is missing")
            inputs += [f for f in files if f not in inputs]
        doc = ws.docs.get(o["path"])
        outputs.append({"path": paths.show(o["path"]), "exists": doc is not None,
                        "status": doc.fm.get("status") if doc else None,
                        "stale": ws.stale_reasons(doc) if doc else [],
                        **({"application": o["app"]} if o.get("app") else {})})
    catalogs = {c: {"path": paths.show(schema.catalogs()[c]["path"]), "items": len(ws.items_in(c)),
                    "required_fields": schema.catalogs()[c].get("required", [])}
                for c in sdef.get("catalogs") or []}

    # The gate after this step: its latest reviewer comments travel with the package.
    gate_info = {}
    route = schema.workflow()["modes"][run["workflow_type"]]["route"] if run else []
    ids_ = [r["id"] for r in route]
    if sid in ids_:
        for item in route[ids_.index(sid) + 1:]:
            if item["kind"] == "use_case_engine":
                break
            if item["kind"] == "gate":
                st = gs(item["id"], run["run_id"])
                gate_info = {"gate": item["id"], "status": st["status"], "comments": st["comments"]}
                break

    overview = {
        "actors": _items(ws, "actors", ("name", "type")),
        "applications": _items(ws, "applications", ("name", "type", "information_architecture", "actors")),
        "business_processes": _items(ws, "business-processes", ("name",)),
        "business_rules": _items(ws, "business-rules", ("name",)),
        "entities": _items(ws, "entities", ("name",)),
        "integrations": _items(ws, "integrations", ("name", "direction")),
        "use_cases": _items(ws, "use-cases", ("name", "actor", "application", "business_process",
                                               "complexity", "risk_level", "risk_flags")),
    }
    pkg = {
        "task": f"{sdef['name']} (master spec Phase {sdef.get('phase')}) for {run['run_id'] if run else '?'}",
        "generated_at": store.now(),
        "step": sid,
        "agent": sdef["agent"],
        "skills": sdef.get("skills", []),
        "workflow_type": run.get("workflow_type") if run else None,
        "project": ws.state.get("project"),
        "inputs": inputs,
        "outputs": outputs,
        "catalogs": catalogs,
        "existing_items": overview,
        "open_questions": [{k: q.get(k) for k in ("id", "question", "target_stakeholder", "priority", "status",
                                                  "blocking", "answer", "related")}
                           for q in ws.items_in("open-questions") if q.get("status") != "CLOSED"],
        "blocking_questions": [q["id"] for q in blocking_questions(ws)],
        "assumptions": [{k: a.get(k) for k in ("id", "statement", "status", "related")}
                        for a in ws.items_in("assumptions") if a.get("status") != "REJECTED"],
        "gate": gate_info,
        "missing": missing,
    }
    if sid == "PLANNING":
        pkg["planning"] = {
            "unplanned_use_cases": unplanned_use_cases(ws),
            "backlog": [{"epic_id": e.get("epic_id"), "name": e.get("name"), "priority": e.get("priority"),
                         "use_cases": [{k: u.get(k) for k in ("use_case_id", "priority", "status", "dependencies")}
                                       for u in as_list(e.get("use_cases")) if isinstance(u, dict)]}
                        for e in ws.epics.values()],
            "plan_command": "tools/ba backlog plan --file <plan.yaml>",
        }
    if sid == "INFORMATION_ARCHITECTURE":
        pkg["information_architecture"] = [
            {"application": a["id"], "name": a.get("name"), "actors": as_list(a.get("actors")),
             "use_cases": [u["id"] for u in ws.items_in("use-cases") if u.get("application") == a["id"]],
             "screens": [{k: s_.get(k) for k in ("id", "name", "route", "use_cases")}
                         for s_ in ws.items_in("screens") if s_.get("application") == a["id"]]}
            for a in ws.ia_applications()]
    out = paths.CONTEXT_DIR / f"{sid}.yaml"
    store.save_yaml(out, pkg)
    return paths.show(paths.rel(out)), missing
