"""BA Knowledge Graph (D-21): generated from catalogs + frontmatter, never hand-edited."""
from __future__ import annotations

from collections import deque
from typing import Dict, List

from . import paths, schema, store
from .ids import CODE_REF_RE, as_list, find_refs, prefix_of
from .workspace import Workspace

SCOPED_NODES = {
    "AC": ("AcceptanceCriterion", "VALIDATES"),
    "VR": ("ValidationRule", "HAS_VALIDATION"),
    "AF": ("AlternateFlow", "HAS_ALTERNATE_FLOW"),
    "EF": ("ErrorFlow", "HAS_ERROR_FLOW"),
    "DEF": ("Defect", "HAS_DEFECT"),
}


def build(ws: Workspace) -> dict:
    nodes: Dict[str, dict] = {}
    edges: Dict[tuple, dict] = {}

    def node(iid, ntype, name, **attrs):
        n = nodes.setdefault(iid, {"id": iid, "type": ntype, "name": name, "artifacts": {}})
        n.update({k: v for k, v in attrs.items() if v is not None})
        return n

    def attach(iid, baseline, rel):
        if iid in nodes:
            lst = nodes[iid]["artifacts"].setdefault(baseline or "TO_BE", [])
            if rel not in lst:
                lst.append(rel)

    def edge(frm, typ, to, source, **attrs):
        e = edges.setdefault((frm, typ, to), {"from": frm, "type": typ, "to": to, "sources": []})
        e.update(attrs)
        if source not in e["sources"]:
            e["sources"].append(source)

    cdefs = schema.catalogs()
    for cname, cdef in cdefs.items():
        meta = (ws.catalog_data.get(cname) or {}).get("meta") or {}
        for item in ws.items_in(cname):
            baseline = item.get("baseline") or meta.get("baseline") or "TO_BE"
            node(item["id"], cdef["node_type"], ws.label(item["id"]), baseline=baseline)
            attach(item["id"], baseline, cdef["path"])
    for sid, rec in ws.steps.items():
        node(sid, "ProcessStep", rec["step"].get("name"), baseline="TO_BE")
        attach(sid, "TO_BE", cdefs["business-processes"]["path"])
    for eid, epic in ws.epics.items():
        node(eid, "Epic", epic.get("name"), priority=epic.get("priority"))
        attach(eid, "TO_BE", "planning/backlog.yaml")

    for cname, cdef in cdefs.items():
        for item in ws.items_in(cname):
            iid = item["id"]
            for f, ref in (cdef.get("refs") or {}).items():
                for v in as_list(item.get(f)):
                    if ref.get("reverse"):
                        edge(v, ref["edge"], iid, cdef["path"])
                    else:
                        edge(iid, ref["edge"], v, cdef["path"])
    for sid, rec in ws.steps.items():
        src = cdefs["business-processes"]["path"]
        edge(rec["bp"], "HAS_STEP", sid, src)
        for uc in as_list(rec["step"].get("use_cases")):
            edge(sid, "TRIGGERS", uc, src)
    for ent in ws.items_in("entities"):
        for r in as_list(ent.get("relationships")):
            if isinstance(r, dict) and r.get("to"):
                edge(ent["id"], "RELATES_TO", r["to"], cdefs["entities"]["path"],
                     cardinality=r.get("cardinality"))
    for eid, epic in ws.epics.items():
        for uc in as_list(epic.get("use_cases")):
            if isinstance(uc, dict):
                edge(eid, "CONTAINS", uc.get("use_case_id"), "planning/backlog.yaml")

    rel_edges = schema.relation_edges()
    for doc in ws.docs.values():
        subject, baseline = doc.id, doc.fm.get("baseline", "TO_BE")
        attach(subject, baseline, doc.rel)
        if subject not in nodes:
            continue
        for k, vals in (doc.fm.get("relations") or {}).items():
            e = rel_edges.get(k)
            for v in as_list(vals) if e else []:
                if e.get("reverse"):
                    edge(v, e["edge"], subject, doc.rel)
                else:
                    edge(subject, e["edge"], v, doc.rel)

    for sid, s in ws.scoped.items():
        ntype, etype = SCOPED_NODES[s["kind"]]
        doc = ws.docs[s["doc"]]
        node(sid, ntype, s["title"], baseline=doc.fm.get("baseline", "TO_BE"))
        attach(sid, doc.fm.get("baseline", "TO_BE"), s["doc"])
        if s["kind"] == "AC":
            edge(sid, etype, s["uc"], s["doc"])
        else:
            edge(s["uc"], etype, sid, s["doc"])
        for ref in sorted(find_refs(s["text"]) - {sid, s["uc"]}):
            if s["kind"] == "AC":
                edge(sid, "COVERS", ref, s["doc"])
            elif s["kind"] == "VR" and prefix_of(ref) in ("BR", "REQ"):
                edge(sid, "ENFORCES", ref, s["doc"])
            else:
                edge(sid, "REFERENCES", ref, s["doc"])

    # QA: TestCase VERIFIES AcceptanceCriterion (master §31)
    for tc, t in ws.test_cases.items():
        doc = ws.docs[t["doc"]]
        node(tc, "TestCase", t["title"], baseline=doc.fm.get("baseline", "TO_BE"))
        attach(tc, doc.fm.get("baseline", "TO_BE"), t["doc"])
        for ref in sorted(find_refs(t["text"]) - {tc, t["uc"]}):
            if prefix_of(ref) == "UC" and "-AC-" in ref:
                edge(tc, "VERIFIES", ref, t["doc"])
            else:
                edge(tc, "COVERS", ref, t["doc"])
    for doc in ws.docs.values():
        if doc.type == "defects":
            for d in as_list(doc.fm.get("defects")):
                if isinstance(d, dict) and d.get("id") in nodes:
                    nodes[d["id"]].update({k: d.get(k) for k in ("classification", "status") if d.get(k)})
                    if d.get("test_case"):
                        edge(d["id"], "FOUND_BY", d["test_case"], doc.rel)

    # Implementation: CodeRef IMPLEMENTS UseCase, CodeRef LOCATED_IN Repository (D-21, D-25);
    # acceptance test files: CodeRef TESTS UseCase (D-38)
    repo_by_name = {r.get("name"): r["id"] for r in ws.items_in("repositories")}
    for doc in ws.docs.values():
        field, etype = {"implementation": ("code_refs", "IMPLEMENTS"),
                        "test-cases": ("test_files", "TESTS")}.get(doc.type, (None, None))
        if not field:
            continue
        for ref in as_list(doc.fm.get(field)):
            m = CODE_REF_RE.match(str(ref))
            if not m:
                continue
            node(ref, "CodeRef", m.group(2), repository=m.group(1))
            attach(ref, doc.fm.get("baseline", "TO_BE"), doc.rel)
            edge(ref, etype, doc.id, doc.rel)
            if m.group(1) in repo_by_name:
                edge(ref, "LOCATED_IN", repo_by_name[m.group(1)], doc.rel)

    for uc, rec in ws.backlog_ucs.items():
        if uc in nodes:
            for f in ("spec_status", "technical_review_status", "coding_status", "testing_status",
                      "documentation_status"):
                if rec["item"].get(f) not in (None, "NOT_STARTED"):
                    nodes[uc][f] = rec["item"][f]
            if rec["item"].get("spec_status") is not None:
                nodes[uc]["spec_status"] = rec["item"]["spec_status"]

    known = set(nodes)
    return {
        "schema_version": 1,
        "generated_at": store.now(),
        "nodes": sorted(nodes.values(), key=lambda n: n["id"]),
        "edges": sorted((e for e in edges.values() if e["from"] in known and e["to"] in known),
                        key=lambda e: (e["from"], e["type"], e["to"])),
    }


def save(ws: Workspace) -> bool:
    g = build(ws)
    old = store.load_json(paths.GRAPH) or {}
    if old.get("nodes") == g["nodes"] and old.get("edges") == g["edges"]:
        return False
    store.save_json(paths.GRAPH, g)
    return True


def neighborhood(g: dict, start: str, depth: int) -> List[str]:
    """Readable traversal in both directions — supports forward and reverse traceability (§39)."""
    by_id = {n["id"]: n for n in g["nodes"]}
    out_adj: Dict[str, list] = {}
    in_adj: Dict[str, list] = {}
    for e in g["edges"]:
        out_adj.setdefault(e["from"], []).append(e)
        in_adj.setdefault(e["to"], []).append(e)
    if start not in by_id:
        return [f"{start} is not in the graph (run `tools/ba sync`)"]

    def label(i):
        n = by_id.get(i, {})
        return f"{i} ({n.get('type', '?')}) {n.get('name') or ''}".rstrip()

    lines = [label(start)]
    seen = {start}
    queue = deque([(start, 0, "  ")])
    while queue:
        cur, d, indent = queue.popleft()
        if d >= depth:
            continue
        for e in out_adj.get(cur, []):
            lines.append(f"{indent}→ {e['type']:<18} {label(e['to'])}")
            if e["to"] not in seen:
                seen.add(e["to"])
                queue.append((e["to"], d + 1, indent + "    "))
        for e in in_adj.get(cur, []):
            lines.append(f"{indent}← {e['type']:<18} {label(e['from'])}")
            if e["from"] not in seen:
                seen.add(e["from"])
                queue.append((e["from"], d + 1, indent + "    "))
    return lines
