"""Loads every catalog, document, the backlog and the state into one in-memory model."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from . import paths, schema, store
from .ids import SCOPED_HEADING_RE, as_list

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
SKIP_DIRS = ("reviews/", "workflow/context/")


def iter_headings(body: str) -> Iterator[Tuple[int, int, str]]:
    """(line index, level, text) for Markdown headings outside code fences."""
    in_fence = False
    for i, line in enumerate(body.split("\n")):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING_RE.match(line)
        if m:
            yield i, len(m.group(1)), m.group(2).strip()


def sections(body: str) -> List[Tuple[int, str, str]]:
    """(level, heading, text-until-next-heading-of-same-or-higher-level)."""
    lines = body.split("\n")
    hs = list(iter_headings(body))
    out = []
    for idx, (i, level, text) in enumerate(hs):
        end = len(lines)
        for j, level2, _ in hs[idx + 1:]:
            if level2 <= level:
                end = j
                break
        out.append((level, text, "\n".join(lines[i + 1:end])))
    return out


def norm_heading(s: str) -> str:
    s = re.sub(r"^\s*\d+(\.\d+)*\.?\s*", "", s).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


class Doc:
    """A Markdown artifact with frontmatter."""

    def __init__(self, path: Path, rel: str, fm: dict, body: str):
        self.path, self.rel, self.fm, self.body = path, rel, fm, body

    @property
    def type(self) -> str:
        return self.fm.get("artifact_type")

    @property
    def id(self) -> str:
        return self.fm.get("id")

    def write_fm(self, updates: dict) -> None:
        self.fm.update(updates)
        store.write_frontmatter(self.path, self.fm, self.body)


class Workspace:
    def __init__(self) -> None:
        self.load_errors: List[Tuple[str, str]] = []
        self.catalog_data: Dict[str, dict] = {}
        self.items: Dict[str, dict] = {}          # id -> {"catalog", "item"}
        self.steps: Dict[str, dict] = {}          # BP-001-S01 -> {"bp", "step"}
        self.epics: Dict[str, dict] = {}
        self.backlog_ucs: Dict[str, dict] = {}    # UC -> {"epic", "item"}
        self.docs: Dict[str, Doc] = {}            # rel path -> Doc
        self.scoped: Dict[str, dict] = {}         # UC-001-AC-01 -> {"doc", "kind", "title", "text", "uc"}
        self._hashes: Dict[str, Optional[str]] = {}
        self.state = store.load_json(paths.STATE, {"runs": []})
        self.backlog = (store.load_yaml(paths.BACKLOG) if paths.BACKLOG.exists() else None) or {}
        self._load_catalogs()
        self._index_backlog()
        self._load_docs()

    # ---------------------------------------------------------------- loading

    def _load_catalogs(self) -> None:
        for name, cdef in schema.catalogs().items():
            p = paths.BA / cdef["path"]
            if not p.exists():
                continue
            try:
                data = store.load_yaml(p) or {}
            except store.BAError as e:
                self.load_errors.append((cdef["path"], str(e)))
                continue
            if not isinstance(data, dict):
                self.load_errors.append((cdef["path"], "catalog must be a mapping with 'meta' and 'items'"))
                continue
            if data.get("items") is None:
                data["items"] = []
            self.catalog_data[name] = data
            for item in data["items"]:
                if not isinstance(item, dict) or not item.get("id"):
                    self.load_errors.append((cdef["path"], f"item without an id: {item!r:.80}"))
                    continue
                iid = item["id"]
                if iid in self.items:
                    other = schema.catalogs()[self.items[iid]["catalog"]]["path"]
                    self.load_errors.append((cdef["path"], f"duplicate ID {iid} (also in {other})"))
                    continue
                self.items[iid] = {"catalog": name, "item": item}
                if name == "business-processes":
                    for st in as_list(item.get("steps")):
                        if isinstance(st, dict) and st.get("id"):
                            self.steps[st["id"]] = {"bp": iid, "step": st}

    def _index_backlog(self) -> None:
        for epic in as_list(self.backlog.get("epics")):
            if not isinstance(epic, dict):
                continue
            self.epics[epic.get("epic_id")] = epic
            for uc in as_list(epic.get("use_cases")):
                if isinstance(uc, dict):
                    self.backlog_ucs[uc.get("use_case_id")] = {"epic": epic.get("epic_id"), "item": uc}

    def _load_docs(self) -> None:
        for p in sorted(paths.BA.rglob("*.md")):
            rel = paths.rel(p)
            if rel.startswith(SKIP_DIRS) or any(part.startswith(".") for part in Path(rel).parts):
                continue
            try:
                fm, body = store.split_frontmatter(p.read_text(encoding="utf-8"))
            except Exception as e:  # malformed YAML in frontmatter
                self.load_errors.append((rel, f"invalid frontmatter: {e}"))
                continue
            if not fm or "artifact_type" not in fm:
                continue
            doc = Doc(p, rel, fm, body)
            self.docs[rel] = doc
            tdef = schema.artifact_type(doc.type) or {}
            kinds = tdef.get("scoped") or []
            for _level, text, sec in sections(body):
                m = SCOPED_HEADING_RE.match(text)
                if not m or m.group(3) not in kinds:
                    continue
                sid = m.group(1)
                if sid in self.scoped:
                    self.load_errors.append((rel, f"{sid} is declared twice (also in {self.scoped[sid]['doc']})"))
                    continue
                self.scoped[sid] = {"doc": rel, "kind": m.group(3), "title": m.group(4).strip(),
                                    "text": sec, "uc": m.group(2)}

    # ---------------------------------------------------------------- lookups

    def item(self, iid: str) -> Optional[dict]:
        rec = self.items.get(iid)
        return rec["item"] if rec else None

    def catalog_of(self, iid: str) -> Optional[str]:
        rec = self.items.get(iid)
        return rec["catalog"] if rec else None

    def items_in(self, cname: str) -> List[dict]:
        return [i for i in as_list((self.catalog_data.get(cname) or {}).get("items")) if isinstance(i, dict)]

    def label(self, iid: str) -> str:
        item = self.item(iid)
        if item:
            cdef = schema.catalogs()[self.catalog_of(iid)]
            return str(item.get(cdef.get("name_field", "name")) or item.get("name") or "")
        if iid in self.steps:
            return str(self.steps[iid]["step"].get("name", ""))
        if iid in self.epics:
            return str(self.epics[iid].get("name", ""))
        if iid in self.scoped:
            return self.scoped[iid]["title"]
        return ""

    def known_ids(self) -> set:
        ids = set(self.items) | set(self.steps) | set(self.scoped)
        ids |= {e for e in self.epics if e}
        ids |= {r.get("run_id") for r in self.runs() if r.get("run_id")}
        return ids

    def runs(self) -> List[dict]:
        return self.state.get("runs") or []

    def run(self, run_id: str) -> Optional[dict]:
        return next((r for r in self.runs() if r.get("run_id") == run_id), None)

    def active_run(self) -> Optional[dict]:
        return self.run(self.state.get("active_run"))

    def run_use_cases(self, run: dict) -> List[str]:
        scope = run.get("scope") or {}
        ucs = as_list(scope.get("use_cases"))
        if not ucs and scope.get("epic") in self.epics:
            ucs = [u.get("use_case_id") for u in as_list(self.epics[scope["epic"]].get("use_cases"))]
        if not ucs:
            ucs = list(self.backlog_ucs)
        return self.by_priority(ucs)

    def by_priority(self, ucs: List[str]) -> List[str]:
        rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        order = list(self.backlog_ucs)

        def key(uc):
            bl = self.backlog_ucs.get(uc)
            if not bl:
                return (9, 9, 9999)
            epic = self.epics.get(bl["epic"]) or {}
            return (rank.get(epic.get("priority"), 5), rank.get(bl["item"].get("priority"), 5), order.index(uc))

        return sorted(ucs, key=key)

    def doc_rel(self, artifact_type: str, uc: str) -> str:
        return schema.artifact_type(artifact_type)["path"].format(UC=uc)

    def input_rel(self, artifact_type: str, uc: str) -> str:
        """Path used when an artifact is an *input* (directory for prototypes)."""
        tdef = schema.artifact_type(artifact_type)
        return (tdef.get("dir") or tdef["path"]).format(UC=uc)

    def docs_under(self, rel: str) -> List[Doc]:
        if rel.endswith("/"):
            return [d for r, d in self.docs.items() if r.startswith(rel)]
        return [self.docs[rel]] if rel in self.docs else []

    # ---------------------------------------------------------------- hashing / staleness

    def hash_rel(self, rel: str) -> Optional[str]:
        if rel not in self._hashes:
            self._hashes[rel] = store.hash_path(paths.BA / rel.rstrip("/"))
        return self._hashes[rel]

    def item_hash(self, iid: str) -> Optional[str]:
        if iid in self.items:
            return store.hash_item(self.items[iid]["item"])
        if iid in self.steps:
            return store.hash_item(self.steps[iid]["step"])
        return None

    def stale_reasons(self, doc: Doc) -> List[str]:
        """Why a document is STALE: an input it was built from has changed (D-12)."""
        out = []
        for e in as_list(doc.fm.get("built_from")):
            if not isinstance(e, dict):
                continue
            if "path" in e:
                cur = self.hash_rel(e["path"])
                if cur is None:
                    out.append(f"input {e['path']} is missing")
                elif cur != e.get("hash"):
                    out.append(f"input {e['path']} changed")
            elif "ref" in e:
                cur = self.item_hash(e["ref"])
                if cur is None:
                    out.append(f"{e['ref']} no longer exists")
                elif cur != e.get("hash"):
                    out.append(f"{e['ref']} changed")
        return out
