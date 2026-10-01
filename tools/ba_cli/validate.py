"""Deterministic artifact checks (D-19). Errors block gate requests."""
from __future__ import annotations

import re
from typing import Callable, Dict, List, Optional, Set

from . import paths, schema, store
from .ids import CODE_REF_RE, as_list, find_refs, id_format_ok, prefix_of
from .workspace import Doc, Workspace, iter_headings, norm_heading, sections

TRANSITION_RE = re.compile(r"^\s*(\(new\)|[A-Za-z0-9_ ]+?)\s*->\s*([A-Za-z0-9_ ]+?)\s*:\s*(\S.*)$")


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
    for f in cdef.get("booleans") or []:
        if item.get(f) is not None and not isinstance(item.get(f), bool):
            msgs.append(f"{iid}: {f} must be true or false")
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
        msgs += _lifecycle_msgs(iid, item.get("lifecycle"))
    return msgs


def _lifecycle_msgs(iid: str, lc) -> List[str]:
    """State model (master §9 3.4) kept on the entity: states, transitions, invalid transitions."""
    if lc is None:
        return []
    if not isinstance(lc, dict) or not as_list(lc.get("states")):
        return [f"{iid}: lifecycle needs a 'states' list"]
    states = {str(x) for x in as_list(lc.get("states"))}
    msgs = []
    for key in ("transitions", "invalid_transitions"):
        for t in as_list(lc.get(key)):
            if isinstance(t, dict):
                frm, to, ev = t.get("from"), t.get("to"), t.get("event")
            else:
                m = TRANSITION_RE.match(str(t))
                if not m:
                    msgs.append(f"{iid}: lifecycle {key} entry {t!r:.60} must read 'FROM -> TO: event' "
                                f"or be a mapping with from / to / event")
                    continue
                frm, to, ev = m.group(1), m.group(2), m.group(3)
            for s_ in (frm, to):
                if s_ not in states and s_ not in ("(new)", None):
                    msgs.append(f"{iid}: lifecycle {key} uses state {s_!r}, which is not in states")
            if not ev:
                msgs.append(f"{iid}: lifecycle {key} {frm} -> {to} needs a triggering event")
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


def _field(text: str, name: str) -> Optional[str]:
    """Value of a '- **Name:** value' line inside a section."""
    m = re.search(r"\*\*" + re.escape(name) + r":?\*\*:?\s*(.+)", text, re.I)
    return m.group(1).strip() if m else None


def _check_test_cases(ws, doc, E, W):
    own = {tc: t for tc, t in ws.test_cases.items() if t["doc"] == doc.rel}
    if not own:
        E(doc.rel, "no test cases — each needs a heading like '### TC-001 — Title' (IDs from `tools/ba next-id TC`)")
    reg = (store.load_json(paths.REGISTRY, {}) or {}).get("counters", {}).get("TC", 0)
    cats = schema.enum("test_category")
    verified = set()
    for tc, t in own.items():
        if int(tc.split("-")[1]) > reg:
            E(doc.rel, f"{tc} was never allocated — get test case IDs from `tools/ba next-id TC`")
        acs = set(re.findall(r"\b" + re.escape(doc.id) + r"-AC-\d{2}\b", _field(t["text"], "Verifies") or ""))
        if not acs:
            E(doc.rel, f"{tc} needs a '**Verifies:** {doc.id}-AC-..' line naming the criteria it tests")
        for ac in acs:
            if ac not in ws.scoped:
                E(doc.rel, f"{tc} verifies {ac}, which is not declared in the acceptance criteria")
        verified |= acs
        cat = (_field(t["text"], "Category") or "").upper().replace(" ", "_")
        if cat not in cats:
            E(doc.rel, f"{tc}: **Category:** must be one of {cats}")
        for f in ("Steps", "Expected"):
            if _field(t["text"], f) is None and not re.search(r"\*\*" + f, t["text"], re.I):
                E(doc.rel, f"{tc} needs a **{f}:** part")
    for ac in sorted(sid for sid, x in ws.scoped.items() if x["kind"] == "AC" and x["uc"] == doc.id):
        if ac not in verified:
            E(doc.rel, f"{ac} is not verified by any test case")
    automated = [tc for tc, t in own.items()
                 if not (_field(t["text"], "Automation") or "").lower().startswith("manual")]
    files = as_list(doc.fm.get("test_files"))
    if automated and not files:
        E(doc.rel, "frontmatter 'test_files' must list the automated acceptance tests as CODE:<repo>/<path> "
                   "(the implementation may not edit them, D-38)")
    for f in files:
        if not CODE_REF_RE.match(str(f)):
            E(doc.rel, f"test file {f!r} must look like CODE:<repo-name>/<path>")
    if automated and not isinstance(doc.fm.get("tests_commit"), dict):
        E(doc.rel, "frontmatter 'tests_commit' must map each REPO-… to the commit that added the acceptance tests")


def _check_test_results(ws, doc, E, W):
    fm = doc.fm
    if fm.get("outcome") not in schema.enum("test_outcome"):
        E(doc.rel, f"frontmatter 'outcome' must be one of {schema.enum('test_outcome')}")
    if not fm.get("executed_at"):
        E(doc.rel, "frontmatter 'executed_at' must say when the tests ran")
    if fm.get("outcome") == "FAILED" and ws.doc_rel("defects", doc.id) not in ws.docs:
        E(doc.rel, f"outcome FAILED needs ba-ai/{ws.doc_rel('defects', doc.id)} with every failure classified")
    if fm.get("outcome") == "BLOCKED" and not fm.get("blocked_reason"):
        E(doc.rel, "outcome BLOCKED needs a 'blocked_reason'")
    mentioned = find_refs(doc.body)
    for tc, t in ws.test_cases.items():
        if t["uc"] == doc.id and tc not in mentioned:
            W(doc.rel, f"{tc} has no result row")


def _check_defects(ws, doc, E, W):
    max_attempts = int(schema.engine().get("max_fix_attempts", 3))
    declared = {sid for sid, x in ws.scoped.items() if x["doc"] == doc.rel and x["kind"] == "DEF"}
    listed = set()
    for d in as_list(doc.fm.get("defects")):
        if not isinstance(d, dict) or not d.get("id"):
            E(doc.rel, f"every entry of 'defects' needs an id ({d!r:.60})")
            continue
        did = d["id"]
        listed.add(did)
        if not re.fullmatch(re.escape(doc.id) + r"-DEF-\d{2}", str(did)):
            E(doc.rel, f"defect id {did} must look like {doc.id}-DEF-01")
        if did not in declared:
            E(doc.rel, f"{did} has no '### {did} — …' section with expected vs actual behaviour")
        if d.get("classification") not in schema.enum("defect_classification"):
            E(doc.rel, f"{did}: classification must be one of {schema.enum('defect_classification')}")
        if d.get("status") not in schema.enum("defect_status"):
            E(doc.rel, f"{did}: status must be one of {schema.enum('defect_status')}")
        n = d.get("fix_attempts", 0)
        if not isinstance(n, int) or n < 0 or n > max_attempts:
            E(doc.rel, f"{did}: fix_attempts must be 0–{max_attempts}")
        if d.get("test_case") and d["test_case"] not in ws.test_cases:
            E(doc.rel, f"{did}: test_case {d['test_case']} is not a declared test case")
    for did in sorted(declared - listed):
        E(doc.rel, f"{did} has a section but is missing from the frontmatter 'defects' list")


def _check_implementation_refs(ws, doc, E, W):
    fm = doc.fm
    repos = {r["id"]: r for r in ws.items_in("repositories")}
    names = {r.get("name"): r["id"] for r in repos.values()}
    for r in as_list(fm.get("repositories")):
        if r not in repos:
            E(doc.rel, f"repositories lists {r}, which is not in workflow/repositories.yaml")
    if not as_list(fm.get("repositories")):
        E(doc.rel, "frontmatter 'repositories' must list the REPO IDs changed")
    if not fm.get("branch"):
        E(doc.rel, "frontmatter 'branch' must name the working branch (ba/<UC>-<slug>, D-25)")
    if not as_list(fm.get("code_refs")):
        E(doc.rel, "frontmatter 'code_refs' must list the changed files as CODE:<repo>/<path>")
    for ref in as_list(fm.get("code_refs")):
        m = CODE_REF_RE.match(str(ref))
        if not m:
            E(doc.rel, f"code ref {ref!r} must look like CODE:<repo-name>/<path>")
        elif m.group(1) not in names:
            E(doc.rel, f"code ref {ref} names repository {m.group(1)!r}, which is not in workflow/repositories.yaml")


IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")


def _check_user_guide(ws, doc, E, W):
    steps = [(t, sec) for _lvl, t, sec in sections(doc.body) if re.match(r"^step\s*\d+", t, re.I)]
    if not steps:
        E(doc.rel, "needs at least one '## Step 1 — …' section")
    for title, sec in steps:
        imgs = IMG_RE.findall(sec)
        if not imgs:
            W(doc.rel, f"'{title}' has no screenshot")
        for src in imgs:
            if not re.match(r"^[a-z]+://", src) and not (doc.path.parent / src).exists():
                E(doc.rel, f"'{title}' shows {src}, which does not exist")


def _check_compiled_spec(ws, doc, E, W):
    from .compile import check
    for m in check(ws, doc):
        E(doc.rel, m)


CHECKS: Dict[str, Callable] = {
    "mermaid": _check_mermaid,
    "screen_sections": _check_screen_sections,
    "prototype_index": _check_prototype_index,
    "api_sections": _check_api_sections,
    "validation_traced": _check_validation_traced,
    "gherkin": _check_gherkin,
    "test_cases": _check_test_cases,
    "test_results": _check_test_results,
    "defects": _check_defects,
    "implementation_refs": _check_implementation_refs,
    "user_guide": _check_user_guide,
    "compiled_spec": _check_compiled_spec,
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
    elif tdef.get("per_application"):
        expected = tdef["path"].format(APP=doc.id)
        if ws.catalog_of(doc.id) != "applications":
            E(doc.rel, f"id {doc.id} is not an application in overview/applications.yaml")
        elif doc.rel != expected:
            E(doc.rel, f"a {doc.type} for {doc.id} must live at ba-ai/{expected}")
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
