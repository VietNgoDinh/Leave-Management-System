"""Deterministic artifact checks (D-19). Errors block gate requests."""
from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional, Set

from . import schema
from .ids import as_list, find_refs, id_format_ok, prefix_of
from .workspace import Doc, Workspace, iter_headings, norm_heading


class Issue:
    def __init__(self, level: str, path: str, msg: str):
        self.level, self.path, self.msg = level, path, msg

    def __str__(self) -> str:
        return f"{self.level:5} ba-ai/{self.path}: {self.msg}"


# ------------------------------------------------------------------ catalog items

def validate_item(ws: Workspace, cname: str, item: dict, known: Set[str]) -> List[str]:
    cdef = schema.catalogs()[cname]
    iid = item.get("id")
    msgs: List[str] = []
    if not id_format_ok(iid, cdef["prefix"]):
        msgs.append(f"{iid}: ID must look like {cdef['prefix']}-NNN")
    for f in cdef.get("required", []):
        if item.get(f) is None or item.get(f) == "":
            msgs.append(f"{iid}: missing required field '{f}'")
    for f, allowed in (cdef.get("enums") or {}).items():
        v = item.get(f)
        if v is not None and v not in allowed:
            msgs.append(f"{iid}: {f}={v!r} must be one of {allowed}")
    for f, allowed in (cdef.get("list_enums") or {}).items():
        for v in as_list(item.get(f)):
            if v not in allowed:
                msgs.append(f"{iid}: {f} value {v!r} must be one of {allowed}")
    if item.get("baseline") is not None and item["baseline"] not in schema.enum("baseline"):
        msgs.append(f"{iid}: baseline must be one of {schema.enum('baseline')}")
    for f, ref in (cdef.get("refs") or {}).items():
        targets = ref["targets"]
        for v in as_list(item.get(f)):
            if not isinstance(v, str):
                msgs.append(f"{iid}: {f} must list IDs, got {v!r}")
            elif v not in known:
                msgs.append(f"{iid}: {f} references unknown ID {v}")
            elif targets != "ANY" and prefix_of(v) not in targets:
                msgs.append(f"{iid}: {f} must reference {'/'.join(targets)}, got {v}")

    if cname == "business-processes":
        for st in as_list(item.get("steps")):
            sid = st.get("id") if isinstance(st, dict) else None
            if not sid or not re.fullmatch(re.escape(str(iid)) + r"-S\d{2}", sid):
                msgs.append(f"{iid}: step id {sid!r} must look like {iid}-S01")
                continue
            if not st.get("name"):
                msgs.append(f"{sid}: missing name")
            if st.get("actor") and st["actor"] not in known:
                msgs.append(f"{sid}: actor {st['actor']} unknown")
            for uc in as_list(st.get("use_cases")):
                if uc not in known:
                    msgs.append(f"{sid}: use case {uc} unknown")
    if cname == "entities":
        for a in as_list(item.get("attributes")):
            if not isinstance(a, dict) or not a.get("name") or not a.get("type"):
                msgs.append(f"{iid}: every attribute needs 'name' and 'type' ({a!r:.60})")
        for r in as_list(item.get("relationships")):
            to = r.get("to") if isinstance(r, dict) else None
            if to not in known or prefix_of(str(to)) != "ENT":
                msgs.append(f"{iid}: relationship target {to!r} must be a known ENT")
            elif not r.get("cardinality"):
                msgs.append(f"{iid}: relationship to {to} needs a cardinality")
    return msgs


# ------------------------------------------------------------------ document checks

def _headings_with(doc: Doc, pattern: str) -> List[str]:
    rx = re.compile(pattern)
    out = []
    for _, _, text in iter_headings(doc.body):
        m = rx.match(text)
        if m:
            out.append(m.group(1))
    return out


def _check_mermaid(ws, doc, E, W):
    if "```mermaid" not in doc.body:
        E(doc.rel, "needs a Mermaid diagram (```mermaid block)")


def _check_screen_sections(ws, doc, E, W):
    scrs = _headings_with(doc, r"^(SCR-\d{3,4})\b")
    if not scrs:
        E(doc.rel, "no screen sections — each screen needs a heading like '### SCR-001 — Name'")
    rel_screens = set(as_list((doc.fm.get("relations") or {}).get("screens")))
    for s in scrs:
        if ws.catalog_of(s) != "screens":
            E(doc.rel, f"{s} is not in ui/screen-catalog.yaml — add it with `tools/ba catalog add screens`")
        if s not in rel_screens:
            W(doc.rel, f"{s} has a section but is missing from relations.screens")


def _check_prototype_index(ws, doc, E, W):
    if not (doc.path.parent / "index.html").exists():
        E(doc.rel, "prototype folder has no index.html")


def _check_api_sections(ws, doc, E, W):
    apis = _headings_with(doc, r"^(API-\d{3,4})\b")
    if not apis:
        E(doc.rel, "no API sections — each API needs a heading like '### API-001 — POST /api/v1/…'")
    rel_apis = set(as_list((doc.fm.get("relations") or {}).get("apis")))
    for a in apis:
        if ws.catalog_of(a) != "apis":
            E(doc.rel, f"{a} is not in technical/api/api-catalog.yaml — add it with `tools/ba catalog add apis`")
        if a not in rel_apis:
            W(doc.rel, f"{a} has a section but is missing from relations.apis")


def _own_scoped(ws, doc, kind):
    return {sid: s for sid, s in ws.scoped.items() if s["doc"] == doc.rel and s["kind"] == kind}


def _check_validation_traced(ws, doc, E, W):
    vrs = _own_scoped(ws, doc, "VR")
    if not vrs:
        W(doc.rel, "no validation rules declared (### UC-xxx-VR-01 — …)")
    for sid, s in vrs.items():
        if s["uc"] != doc.id:
            E(doc.rel, f"{sid} belongs to {s['uc']}, not {doc.id}")
        if not re.search(r"\b(BR|REQ)-\d{3,4}\b", s["text"]):
            E(doc.rel, f"{sid} must cite the business rule (BR-…) or requirement (REQ-…) it enforces")
    for kind in ("AF", "EF"):
        for sid, s in _own_scoped(ws, doc, kind).items():
            if s["uc"] != doc.id:
                E(doc.rel, f"{sid} belongs to {s['uc']}, not {doc.id}")


VAGUE_RE = re.compile(r"\b(works? (correctly|properly|as expected|fine)|user[- ]friendly|"
                      r"intuitive|fast enough|quickly|appropriate(ly)?|etc\.?)(?=\W|$)", re.I)


def _check_gherkin(ws, doc, E, W):
    acs = _own_scoped(ws, doc, "AC")
    if not acs:
        E(doc.rel, "no acceptance criteria — each needs a heading like '### UC-001-AC-01 — Title'")
    for sid, s in acs.items():
        if s["uc"] != doc.id:
            E(doc.rel, f"{sid} belongs to {s['uc']}, not {doc.id}")
        missing = [k for k in ("Given", "When", "Then") if not re.search(rf"\b{k}\b", s["text"])]
        if missing:
            E(doc.rel, f"{sid} is not testable — missing {', '.join(missing)}")
        vague = VAGUE_RE.search(s["title"] + "\n" + s["text"])
        if vague:
            W(doc.rel, f"{sid} uses vague wording '{vague.group(0)}' — state an observable result")


CHECKS: Dict[str, Callable] = {
    "mermaid": _check_mermaid,
    "screen_sections": _check_screen_sections,
    "prototype_index": _check_prototype_index,
    "api_sections": _check_api_sections,
    "validation_traced": _check_validation_traced,
    "gherkin": _check_gherkin,
}


def _validate_doc(ws: Workspace, doc: Doc, known: Set[str], E, W) -> None:
    tdef = schema.artifact_type(doc.type)
    if not tdef:
        E(doc.rel, f"unknown artifact_type '{doc.type}'")
        return
    fm = doc.fm
    for k in schema.artifacts()["required_frontmatter"]:
        if k not in fm:
            E(doc.rel, f"frontmatter is missing '{k}'")
    for key, enum_name in (("status", "artifact_status"), ("baseline", "baseline"), ("origin", "origin")):
        if key in fm and fm[key] not in schema.enum(enum_name):
            E(doc.rel, f"{key}={fm[key]!r} must be one of {schema.enum(enum_name)}")

    if tdef.get("per_use_case"):
        expected = tdef["path"].format(UC=doc.id)
        if doc.rel != expected:
            E(doc.rel, f"a {doc.type} for {doc.id} must live at ba-ai/{expected}")
        if ws.catalog_of(doc.id) != "use-cases":
            E(doc.rel, f"id {doc.id} is not a use case in overview/use-cases.yaml")
        if not fm.get("built_from"):
            E(doc.rel, f"not stamped — run `tools/ba stamp ba-ai/{doc.rel}`")
        if not isinstance(fm.get("relations"), dict):
            E(doc.rel, "frontmatter 'relations' must be a mapping")
    else:
        if tdef.get("path") and doc.rel != tdef["path"]:
            E(doc.rel, f"a {doc.type} must live at ba-ai/{tdef['path']}")
        if tdef.get("path_regex") and not re.match(tdef["path_regex"], doc.rel):
            E(doc.rel, f"path does not match {tdef['path_regex']}")
        if tdef.get("id") and doc.id != tdef["id"]:
            E(doc.rel, f"id must be {tdef['id']}")
        if tdef.get("id_regex") and not re.match(tdef["id_regex"], str(doc.id)):
            E(doc.rel, f"id must match {tdef['id_regex']}")

    relations = fm.get("relations") or {}
    if isinstance(relations, dict):
        allowed = schema.relation_edges()
        for k, vals in relations.items():
            if k not in allowed:
                E(doc.rel, f"unknown relation key '{k}' (allowed: {', '.join(allowed)})")
            for v in as_list(vals):
                if v not in known:
                    E(doc.rel, f"relations.{k} references unknown ID {v}")
    for key, prefix in (("open_questions", "Q"), ("assumptions", "ASM")):
        for v in as_list(fm.get(key)):
            if v not in known or prefix_of(str(v)) != prefix:
                E(doc.rel, f"{key} lists unknown {prefix} ID {v}")

    present = {norm_heading(t) for _, _, t in iter_headings(doc.body)}
    for h in tdef.get("headings", []):
        if norm_heading(h) not in present:
            E(doc.rel, f"missing section '{h}'")

    for ref in sorted(find_refs(doc.body)):
        if ref not in known:
            E(doc.rel, f"mentions unknown ID {ref} — never invent IDs; allocate with `tools/ba catalog add` or `tools/ba next-id`")

    for check in tdef.get("checks", []):
        CHECKS[check](ws, doc, E, W)

    for reason in ws.stale_reasons(doc):
        W(doc.rel, f"STALE — {reason}")


# ------------------------------------------------------------------ backlog / state

def _validate_backlog(ws: Workspace, E, W) -> None:
    rel = "planning/backlog.yaml"
    item_status = schema.enum("backlog_item_status")
    stage_status = schema.enum("backlog_stage_status")
    prio = schema.enum("priority")
    for eid, epic in ws.epics.items():
        if not id_format_ok(eid, "EPIC"):
            E(rel, f"epic id {eid!r} must look like EPIC-NNN")
        if epic.get("priority") not in prio:
            E(rel, f"{eid}: priority must be one of {prio}")
        if epic.get("status") not in item_status:
            E(rel, f"{eid}: status must be one of {item_status}")
    for uc, bl in ws.backlog_ucs.items():
        item = bl["item"]
        if ws.catalog_of(uc) != "use-cases":
            E(rel, f"{uc} is not in overview/use-cases.yaml")
        if item.get("status") not in item_status:
            E(rel, f"{uc}: status must be one of {item_status}")
        if item.get("priority") not in prio:
            E(rel, f"{uc}: priority must be one of {prio}")
        for f in ("ui_status", "spec_status", "technical_review_status", "coding_status",
                  "testing_status", "documentation_status"):
            if item.get(f) not in stage_status:
                E(rel, f"{uc}: {f} must be one of {stage_status}")
        for dep in as_list(item.get("dependencies")):
            if dep not in ws.backlog_ucs:
                E(rel, f"{uc}: dependency {dep} is not in the backlog")


def _validate_state(ws: Workspace, E) -> None:
    rel = "workflow/state.json"
    modes = schema.workflow()["modes"]
    for r in ws.runs():
        rid = r.get("run_id")
        if not id_format_ok(rid, "RUN"):
            E(rel, f"run id {rid!r} must look like RUN-NNN")
        if r.get("workflow_type") not in modes:
            E(rel, f"{rid}: workflow_type must be one of {list(modes)}")
        if r.get("status") not in schema.enum("run_status"):
            E(rel, f"{rid}: status must be one of {schema.enum('run_status')}")
    if ws.state.get("active_run") and not ws.active_run():
        E(rel, f"active_run {ws.state.get('active_run')} is not a run")


# ------------------------------------------------------------------ entry point

def validate(ws: Workspace, only: Optional[Set[str]] = None) -> List[Issue]:
    issues: List[Issue] = []

    def E(path, msg):
        issues.append(Issue("ERROR", path, msg))

    def W(path, msg):
        issues.append(Issue("WARN", path, msg))

    for rel, msg in ws.load_errors:
        E(rel, msg)
    known = ws.known_ids()
    for cname, data in ws.catalog_data.items():
        cdef = schema.catalogs()[cname]
        meta = data.get("meta") or {}
        if meta.get("status") is not None and meta["status"] not in schema.enum("artifact_status"):
            E(cdef["path"], f"meta.status must be one of {schema.enum('artifact_status')}")
        for item in data["items"]:
            if isinstance(item, dict) and item.get("id"):
                for m in validate_item(ws, cname, item, known):
                    E(cdef["path"], m)
    _validate_backlog(ws, E, W)
    _validate_state(ws, E)
    for doc in ws.docs.values():
        _validate_doc(ws, doc, known, E, W)
    if only is not None:
        issues = [i for i in issues if i.path in only]
    return issues


def errors_by_rel(issues: List[Issue]) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for i in issues:
        if i.level == "ERROR":
            out.setdefault(i.path, []).append(i.msg)
    return out
