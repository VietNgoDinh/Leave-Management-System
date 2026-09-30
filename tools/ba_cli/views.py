"""Readable Markdown views of the overview and requirements catalogs, generated next to each YAML file.

The YAML stays the source of truth. A view has no frontmatter, so it is not an artifact:
it is never validated, hashed or put under a gate. `tools/ba sync` regenerates it.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import paths, schema, store
from .ids import as_list
from .workspace import Workspace

VIEW_PREFIXES = ("overview/", "requirements/")     # catalogs under these folders get a view
SUFFIX = ".view.md"
BACKLOG_VIEW = "planning/backlog" + SUFFIX
ID_RE = re.compile(r"^[A-Z]+-\d{3,4}$")
COMPACT_MAX = 24                   # longer list entries are shown as bullets
HEADING_MAX = 80                   # longer names go under the heading instead of in it

# Summary table columns per catalog: (header, field). Fields not listed go to the item's detail section.
SUMMARY: Dict[str, List[Tuple[str, str]]] = {
    "requirements": [("Name", "name"), ("Priority", "priority"), ("Description", "description"), ("Source", "source")],
    "open-questions": [("Question", "question"), ("Priority", "priority"), ("Status", "status"),
                       ("Stakeholder", "target_stakeholder")],
    "assumptions": [("Statement", "statement"), ("Status", "status"), ("Reason", "reason")],
    "actors": [("Name", "name"), ("Type", "type"), ("Description", "description")],
    "applications": [("Name", "name"), ("Type", "type"), ("Actors", "actors"), ("Description", "description")],
    "business-processes": [("Name", "name"), ("Trigger", "trigger"), ("Actors", "actors")],
    "business-rules": [("Name", "name"), ("Rule", "description"), ("Source", "source")],
    "entities": [("Name", "name"), ("Owner", "owner"), ("Description", "description")],
    "integrations": [("Name", "name"), ("Direction", "direction"), ("Owner", "owner"), ("Purpose", "purpose")],
    "use-cases": [("Name", "name"), ("Actor", "actor"), ("Process", "business_process"),
                  ("Complexity", "complexity"), ("Risk", "risk_level"), ("Risk flags", "risk_flags")],
}
DEFAULT_SUMMARY = [("Name", "name")]
HIDDEN = ("id", "baseline")
ER_CARDINALITY = {"N:1": "}o--||", "1:N": "||--o{", "N:M": "}o--o{", "M:N": "}o--o{", "1:1": "||--||"}


def view_rel(catalog_rel: str) -> str:
    return re.sub(r"\.ya?ml$", "", catalog_rel) + SUFFIX


def viewed_catalogs() -> Dict[str, str]:
    """catalog name -> path of its view, relative to ba-ai/."""
    return {name: view_rel(cdef["path"]) for name, cdef in schema.catalogs().items()
            if cdef["path"].startswith(VIEW_PREFIXES)}


def _label(field: str) -> str:
    text = field.replace("_", " ").strip()
    return "ID" if text.lower() == "id" else text[:1].upper() + text[1:]


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


class _Renderer:
    def __init__(self, ws: Workspace, cname: str, views: Dict[str, str]):
        self.ws, self.cname, self.views = ws, cname, views
        self.cdef = schema.catalogs()[cname]
        self.rel = views[cname]
        self.items = ws.items_in(cname)
        self.columns = SUMMARY.get(cname, DEFAULT_SUMMARY)
        self.name_field = self.cdef.get("name_field", "name")

    # ------------------------------------------------------------ values

    def _href(self, iid: str) -> Optional[str]:
        target = self.views.get(self.ws.catalog_of(iid) or "")
        if not target:
            return None
        if target == self.rel:
            return "#" + iid
        return os.path.relpath(target, os.path.dirname(self.rel)).replace(os.sep, "/") + "#" + iid

    def _is_ref(self, v: Any) -> bool:
        return isinstance(v, str) and bool(ID_RE.match(v)) and self.ws.item(v) is not None

    def _ref(self, iid: str, short: bool) -> str:
        name, href = self.ws.label(iid), self._href(iid)
        if short:
            return f"[{name}]({href})" if href else f"{name} ({iid})"
        return f"[{iid}]({href}) {name}" if href else f"{iid} {name}"

    def _inline(self, v: Any, short: bool = False) -> str:
        if v is None:
            return ""
        if self._is_ref(v):
            return self._ref(v, short)
        if isinstance(v, dict):
            return "; ".join(f"{_label(k)}: {self._inline(x, short)}" for k, x in v.items())
        if isinstance(v, list):
            return ", ".join(self._inline(x, short) for x in v)
        return str(v).strip()

    def _compact(self, values: List[Any]) -> bool:
        return all(not isinstance(x, (dict, list)) and not self._is_ref(x) and len(str(x)) <= COMPACT_MAX
                   for x in values)

    def _table(self, rows: List[dict]) -> List[str]:
        keys: List[str] = []
        for r in rows:
            keys += [k for k in r if k not in keys]
        out = ["| " + " | ".join(_label(k) for k in keys) + " |", "|" + "---|" * len(keys)]
        for r in rows:
            out.append("| " + " | ".join(_cell(self._inline(r.get(k), short=True)) for k in keys) + " |")
        return out

    def _bullets(self, label: str, v: Any, level: int) -> List[str]:
        pad = "  " * level
        head = f"{pad}- **{label}:**"
        if isinstance(v, dict):
            out = [head]
            for k, x in v.items():
                out += self._bullets(_label(k), x, level + 1)
            return out
        if isinstance(v, list) and not self._compact(v):
            return [head] + [f"{pad}  - {self._inline(x)}" for x in v]
        return [f"{head} {self._inline(v)}"]

    def _block(self, label: str, v: Any) -> List[str]:
        head = f"**{label}:**"
        if isinstance(v, dict):
            out = [head, ""]
            for k, x in v.items():
                out += self._bullets(_label(k), x, 0)
            return out + [""]
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            return [head, ""] + self._table(v) + [""]
        if isinstance(v, list) and not self._compact(v):
            return [head, ""] + [f"- {self._inline(x)}" for x in v] + [""]
        return [f"{head} {self._inline(v)}", ""]

    # ------------------------------------------------------------ sections

    def _detail_fields(self, item: dict) -> List[str]:
        shown = {f for _, f in self.columns} | set(HIDDEN) | {self.name_field}
        return [k for k, v in item.items() if k not in shown and v not in (None, "", [], {})]

    def _summary(self, with_details: set) -> List[str]:
        headers = ["ID"] + [h for h, _ in self.columns]
        out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
        for item in self.items:
            iid = item["id"]
            first = f"[{iid}](#{iid})" if iid in with_details else f'<a id="{iid}"></a>{iid}'
            cells = [first]
            for _, f in self.columns:
                v = item.get(f)
                if isinstance(v, list):
                    cells.append("<br>".join(_cell(self._inline(x, short=True)) for x in v))
                else:
                    cells.append(_cell(self._inline(v, short=True)))
            out.append("| " + " | ".join(cells) + " |")
        return out

    def _er_diagram(self) -> List[str]:
        def node(iid: str) -> str:
            return re.sub(r"\W+", "_", self.ws.label(iid)).strip("_") or iid.replace("-", "_")

        lines = []
        for item in self.items:
            for r in as_list(item.get("relationships")):
                if not isinstance(r, dict) or not self._is_ref(r.get("to")):
                    continue
                arrow = ER_CARDINALITY.get(str(r.get("cardinality", "")).upper().replace(" ", ""))
                if arrow:
                    text = str(r.get("description") or r.get("name") or "relates to").replace('"', "'")
                    lines.append(f'    {node(item["id"])} {arrow} {node(r["to"])} : "{text}"')
        if not lines:
            return []
        return ["## Relationships", "", "```mermaid", "erDiagram"] + lines + ["```", ""]

    def render(self) -> str:
        meta = (self.ws.catalog_data.get(self.cname) or {}).get("meta") or {}
        source = Path(self.cdef["path"]).name
        title = meta.get("title") or self.cdef.get("title") or self.cname
        facts = [f"{len(self.items)} item{'' if len(self.items) == 1 else 's'}"]
        if meta.get("status"):
            facts.append(f"Status: {meta['status']}")
        facts += [f"{g}: {s}" for g, s in (meta.get("review") or {}).items()]
        out = [
            f"<!-- GENERATED by tools/ba from {source}. Do not edit: change the YAML, then run `tools/ba sync`. -->",
            f"# {title}",
            "",
            " · ".join(facts),
            "",
            f"_Read-only view of [{source}]({source}), regenerated by `tools/ba sync`. Edit the YAML, not this file._",
            "",
        ]
        if not self.items:
            return "\n".join(out + ["No items yet.", ""])

        details = {i["id"]: self._detail_fields(i) for i in self.items}
        with_details = {iid for iid, fields in details.items() if fields}
        out += ["## Summary", ""] + self._summary(with_details) + [""]
        if self.cname == "entities":
            out += self._er_diagram()
        if with_details:
            out += ["## Details", ""]
            for item in self.items:
                iid = item["id"]
                if iid not in with_details:
                    continue
                name = str(item.get(self.name_field) or "")
                out.append(f'<a id="{iid}"></a>')
                if len(name) > HEADING_MAX:
                    out += [f"### {iid}", "", name, ""]
                else:
                    out += [f"### {iid} — {name}".rstrip(" —"), ""]
                for f in details[iid]:
                    out += self._block(_label(f), item[f])
        return "\n".join(out).rstrip("\n") + "\n"


def _render_backlog(ws: Workspace, views: Dict[str, str]) -> str:
    """Epics and their use cases, in backlog order, with where each use case stands."""
    here = os.path.dirname(BACKLOG_VIEW)

    def link(rel: str, anchor: str = "") -> str:
        return os.path.relpath(rel, here).replace(os.sep, "/") + (f"#{anchor}" if anchor else "")

    def ref(iid: str) -> str:
        target = views.get(ws.catalog_of(iid) or "")
        return f"[{iid}]({link(target, iid)})" if target else iid

    def names(value: Any) -> str:
        return "<br>".join(_cell(ws.label(a) or str(a)) for a in as_list(value))

    def artifact(shown: Optional[str], text: str) -> Optional[str]:
        if not shown:
            return None
        return f"[{text}]({link(shown[len('ba-ai/'):] if shown.startswith('ba-ai/') else shown)})"

    source = paths.BACKLOG.name
    total = len(ws.backlog_ucs)
    out = [
        f"<!-- GENERATED by tools/ba from {source}. Do not edit: change the YAML, then run `tools/ba sync`. -->",
        f"# {(ws.backlog.get('meta') or {}).get('title') or 'Delivery Backlog'}",
        "",
        f"{len(ws.epics)} epic{'' if len(ws.epics) == 1 else 's'} · {total} use case{'' if total == 1 else 's'}",
        "",
        f"_Read-only view of [{source}]({source}), regenerated by `tools/ba sync`. In the YAML the BA edits "
        "priority, status (BACKLOG, READY, BLOCKED) and dependencies; the other fields are derived._",
        "",
    ]
    if not ws.epics:
        return "\n".join(out + ["No epics yet.", ""])

    out += ["## Epics", "", "| ID | Epic | Priority | Status | Use cases |", "|---|---|---|---|---|"]
    for eid, epic in ws.epics.items():
        out.append(f"| [{eid}](#{eid}) | {_cell(str(epic.get('name') or ''))} | {epic.get('priority') or ''} | "
                   f"{epic.get('status') or ''} | {len(as_list(epic.get('use_cases')))} |")
    out.append("")

    for eid, epic in ws.epics.items():
        out += [f'<a id="{eid}"></a>', f"## {eid} — {epic.get('name') or ''}", "",
                f"Priority: {epic.get('priority') or ''} · Status: {epic.get('status') or ''}", "",
                "| ID | Use case | Actor | Priority | Status | Now at | Screens | Spec | Depends on | Documents |",
                "|---|---|---|---|---|---|---|---|---|---|"]
        for uc in as_list(epic.get("use_cases")):
            if not isinstance(uc, dict):
                continue
            docs = [d for d in (artifact(uc.get("ui_artifact"), "screens"),
                                artifact(uc.get("technical_artifact"), "API"),
                                artifact(uc.get("spec_artifact"), "spec")) if d]
            cells = [
                ref(str(uc.get("use_case_id"))),
                _cell(str(uc.get("name") or ws.label(str(uc.get("use_case_id"))))),
                names(uc.get("actor")),
                str(uc.get("priority") or ""),
                str(uc.get("status") or ""),
                _cell(str(uc.get("workflow_note") or uc.get("current_step") or "")),
                str(uc.get("ui_status") or ""),
                str(uc.get("spec_status") or ""),
                ", ".join(ref(d) for d in as_list(uc.get("dependencies"))),
                " · ".join(docs),
            ]
            out.append("| " + " | ".join(cells) + " |")
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"


def write_all(ws: Workspace) -> List[str]:
    """(Re)write every catalog view and the backlog view. Returns the views that changed, relative to ba-ai/."""
    views = {c: rel for c, rel in viewed_catalogs().items() if c in ws.catalog_data}
    texts = {rel: _Renderer(ws, cname, views).render() for cname, rel in views.items()}
    if paths.BACKLOG.exists():
        texts[BACKLOG_VIEW] = _render_backlog(ws, views)
    changed = []
    for rel, text in texts.items():
        p = paths.BA / rel
        if not p.exists() or p.read_text(encoding="utf-8") != text:
            store.write_atomic(p, text)
            changed.append(rel)
    return changed
