"""ID formats (D-14), normalisation, allocation and catalog editing."""
from __future__ import annotations

import re
from typing import Any, List, Set

from . import paths, schema, store
from .store import BAError

GLOBAL_PREFIXES = ("REQ", "EPIC", "BP", "ACT", "UC", "SCR", "BR", "ENT", "API", "SVC",
                   "APP", "INT", "REPO", "TC", "Q", "ASM", "CR", "RUN")
_ALT = "|".join(sorted(GLOBAL_PREFIXES, key=len, reverse=True))
GLOBAL_RE = re.compile(r"\b(" + _ALT + r")-(\d{3,4})\b")
SCOPED_KINDS = "AC|VR|AF|EF|DEF"
SCOPED_RE = re.compile(r"\b(UC-\d{3,4})-(" + SCOPED_KINDS + r")-(\d{2})\b")
STEP_RE = re.compile(r"\b(BP-\d{3,4})-S(\d{2})\b")
SCOPED_HEADING_RE = re.compile(r"^((UC-\d{3,4})-(" + SCOPED_KINDS + r")-\d{2})\b[\s—–:\-]*(.*)$")
TC_HEADING_RE = re.compile(r"^(TC-\d{3,4})\b[\s—–:\-]*(.*)$")
CODE_REF_RE = re.compile(r"^CODE:([A-Za-z0-9._-]+)/(\S+)$")
GATE_RE = re.compile(r"^GATE-\d{2}$")


def as_list(v: Any) -> list:
    if v is None or v == "":
        return []
    return v if isinstance(v, list) else [v]


def prefix_of(i: str) -> str:
    return i.split("-", 1)[0]


def id_format_ok(i: Any, prefix: str) -> bool:
    return isinstance(i, str) and re.fullmatch(prefix + r"-\d{3,4}", i) is not None


def normalize_id(s: str) -> str:
    """UC-7 / uc-07 → UC-007, UC-1-AC-1 → UC-001-AC-01, GATE-3 → GATE-03."""
    s = (s or "").strip().upper()
    m = re.fullmatch(r"([A-Z]+)-(\d+)(?:-(" + SCOPED_KINDS + r")-(\d+)|-S(\d+))?", s)
    if not m:
        return s
    p, n, sp, sn, step = m.groups()
    if p == "GATE":
        return f"GATE-{int(n):02d}"
    out = f"{p}-{int(n):03d}"
    if sp:
        out += f"-{sp}-{int(sn):02d}"
    elif step:
        out += f"-S{int(step):02d}"
    return out


def find_refs(text: str) -> Set[str]:
    """Every ID mentioned in a piece of text."""
    refs = {m.group(0) for m in GLOBAL_RE.finditer(text)}
    refs |= {m.group(0) for m in SCOPED_RE.finditer(text)}
    refs |= {m.group(0) for m in STEP_RE.finditer(text)}
    return refs


def _registry() -> dict:
    return store.load_json(paths.REGISTRY, {"schema_version": 1, "counters": {}})


def next_id(prefix: str) -> str:
    """Allocate the next global ID. Lock-protected, so parallel agents never collide."""
    from .workspace import Workspace
    prefix = prefix.upper()
    if prefix not in GLOBAL_PREFIXES:
        raise BAError(f"unknown ID prefix {prefix}; one of: {', '.join(GLOBAL_PREFIXES)}")
    with store.locked():
        ws = Workspace()
        reg = _registry()
        used = [int(i.split("-")[1]) for i in ws.known_ids() if id_format_ok(i, prefix)]
        n = max([reg["counters"].get(prefix, 0)] + used) + 1
        reg["counters"][prefix] = n
        store.save_json(paths.REGISTRY, reg)
    return f"{prefix}-{n:03d}"


def _gated_catalog_check(ws, cname: str, force: bool) -> None:
    """Editing a catalog under an APPROVED run gate invalidates that approval."""
    from . import gates
    rel = schema.catalogs()[cname]["path"]
    run = ws.active_run()
    if not run:
        return
    for gid, g in schema.workflow()["gates"].items():
        if g.get("subject") == "RUN" and rel in g.get("artifacts", []):
            if gates.status(ws, gid, run["run_id"])["status"] == "APPROVED" and not force:
                raise BAError(
                    f"{rel} is covered by {gid}, which is APPROVED. Changing it invalidates that "
                    f"approval and needs the BA to re-approve. Only do this on the BA's instruction, "
                    f"with --force-gated.")


def catalog_add(cname: str, data: dict, force_gated: bool = False) -> str:
    from .validate import validate_item
    from .workspace import Workspace
    cdefs = schema.catalogs()
    if cname not in cdefs:
        raise BAError(f"unknown catalog '{cname}'; one of: {', '.join(cdefs)}")
    if not isinstance(data, dict):
        raise BAError("--data must be a mapping (JSON or YAML object)")
    cdef = cdefs[cname]
    with store.locked():
        ws = Workspace()
        _gated_catalog_check(ws, cname, force_gated)
        item = dict(data)
        if item.get("id"):
            item["id"] = normalize_id(item["id"])
            if item["id"] in ws.known_ids():
                raise BAError(f"{item['id']} already exists — use `tools/ba catalog update {item['id']}`")
            probe_id = item["id"]
        else:
            probe_id = f"{cdef['prefix']}-000"
            item = {"id": probe_id, **item}
        item.setdefault("baseline", "TO_BE")
        if cname == "business-processes":
            # Steps given without an id are numbered <BP>-S01, -S02, … once the BP ID is known.
            for n, st in enumerate(as_list(item.get("steps")), 1):
                if isinstance(st, dict) and not st.get("id"):
                    st["id"] = f"{probe_id}-S{n:02d}"
        msgs = validate_item(ws, cname, item, ws.known_ids() | {probe_id})
        if msgs:
            raise BAError("item rejected:\n  " + "\n  ".join(msgs))
        if probe_id.endswith("-000"):
            item["id"] = next_id(cdef["prefix"])
            for st in as_list(item.get("steps")):
                if isinstance(st, dict) and str(st.get("id", "")).startswith(probe_id + "-S"):
                    st["id"] = item["id"] + st["id"][len(probe_id):]
        cat = ws.catalog_data.get(cname) or {
            "meta": {"artifact_type": "catalog", "catalog": cname,
                     "title": cdef.get("title", cname), "status": "DRAFT",
                     "baseline": "TO_BE", "origin": "AI"},
            "items": [],
        }
        cat["items"].append(item)
        store.save_yaml(paths.BA / cdef["path"], cat)
    return item["id"]


def catalog_init(cname: str) -> str:
    """Create an empty catalog file, so a gate can record that there are no items (e.g. no integrations)."""
    from .workspace import Workspace
    cdefs = schema.catalogs()
    if cname not in cdefs:
        raise BAError(f"unknown catalog '{cname}'; one of: {', '.join(cdefs)}")
    cdef = cdefs[cname]
    with store.locked():
        ws = Workspace()
        if cname in ws.catalog_data:
            return f"ba-ai/{cdef['path']} already exists ({len(ws.items_in(cname))} items)"
        _gated_catalog_check(ws, cname, False)
        store.save_yaml(paths.BA / cdef["path"], {
            "meta": {"artifact_type": "catalog", "catalog": cname, "title": cdef.get("title", cname),
                     "status": "DRAFT", "baseline": "TO_BE", "origin": "AI"},
            "items": []})
    return f"created ba-ai/{cdef['path']} with no items"


def catalog_update(iid: str, data: dict, force_gated: bool = False) -> str:
    """Merge fields into an existing item. A field set to null is removed."""
    from .validate import validate_item
    from .workspace import Workspace
    iid = normalize_id(iid)
    with store.locked():
        ws = Workspace()
        rec = ws.items.get(iid)
        if not rec:
            raise BAError(f"{iid} is not a catalog item")
        cname = rec["catalog"]
        _gated_catalog_check(ws, cname, force_gated)
        cat = ws.catalog_data[cname]
        item = next(i for i in cat["items"] if isinstance(i, dict) and i.get("id") == iid)
        new = dict(item)
        for k, v in data.items():
            if k == "id":
                continue
            if v is None:
                new.pop(k, None)
            else:
                new[k] = v
        msgs = validate_item(ws, cname, new, ws.known_ids())
        if msgs:
            raise BAError("update rejected:\n  " + "\n  ".join(msgs))
        item.clear()
        item.update(new)
        store.save_yaml(paths.BA / schema.catalogs()[cname]["path"], cat)
    return iid


def find(ws, text: str) -> List[tuple]:
    """Rule 4 — search existing catalog items before creating new ones."""
    terms = [t for t in text.lower().split() if t]
    hits = []
    for iid, rec in ws.items.items():
        item = rec["item"]
        name = ws.label(iid).lower()
        blob = " ".join(str(v) for v in item.values() if isinstance(v, (str, int))).lower()
        matched = sum(1 for t in terms if t in blob)
        if matched:
            score = matched * 10 + sum(3 for t in terms if t in name)
            hits.append((score, matched, iid, rec["catalog"], ws.label(iid)))
    if not hits:
        return []
    best = max(h[1] for h in hits)
    hits = [h for h in hits if h[1] == best]   # only items matching the most terms
    hits.sort(key=lambda h: (-h[0], h[2]))
    return [(h[0], h[2], h[3], h[4]) for h in hits]
