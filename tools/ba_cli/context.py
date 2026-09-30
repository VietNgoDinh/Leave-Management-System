"""Step 5.1 — build the minimal context package for one use case (master spec §35)."""
from __future__ import annotations

from typing import List, Tuple

from . import paths, schema, store
from .engine import GateCache
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
            if st["comments"]:
                gate_info[gid]["latest_comments"] = st["comments"]

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
        "missing": missing,
    }
    out = paths.CONTEXT_DIR / f"{uc}.yaml"
    store.save_yaml(out, pkg)
    return paths.show(paths.rel(out)), missing
