"""Human gates: requests freeze content hashes, decisions come only from humans (D-09 – D-11)."""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Dict, List, Optional

from . import paths, schema, store
from .store import BAError
from .workspace import Workspace


def gate_def(gid: str) -> dict:
    g = schema.gate(gid)
    if not g:
        raise BAError(f"unknown gate {gid}; gates: {', '.join(schema.workflow()['gates'])}")
    return g


def check_subject(ws: Workspace, gid: str, subject: str) -> None:
    kind = gate_def(gid)["subject"]
    if kind == "RUN" and not ws.run(subject):
        runs = ", ".join(r["run_id"] for r in ws.runs()) or "none"
        raise BAError(f"{gid} is a run-level gate; {subject} is not a run (runs: {runs})")
    if kind == "USE_CASE" and ws.catalog_of(subject) != "use-cases":
        raise BAError(f"{gid} is a use-case gate; {subject} is not a use case")


def artifact_rels(gid: str, subject: str) -> List[str]:
    return [a.format(UC=subject) for a in gate_def(gid).get("artifacts", [])]


def current_hashes(ws: Workspace, gid: str, subject: str) -> Dict[str, Optional[str]]:
    return {rel: ws.hash_rel(rel) for rel in artifact_rels(gid, subject)}


def _request_file(gid: str, subject: str) -> Path:
    return paths.REQUESTS / subject / f"{gid}.json"


def load_requests(gid: str, subject: str) -> List[dict]:
    return (store.load_json(_request_file(gid, subject)) or {}).get("requests", [])


def load_decisions(gid: str, subject: str) -> List[dict]:
    d = paths.DECISIONS / subject
    if not d.exists():
        return []
    decs = [store.load_json(f) for f in sorted(d.glob(f"{gid}-*.json"))]
    return sorted(decs, key=lambda x: x.get("decided_at", ""))


def stale_in(ws: Workspace, rels: List[str]) -> List[str]:
    out = []
    for rel in rels:
        for doc in ws.docs_under(rel):
            out += [f"{doc.rel}: {r}" for r in ws.stale_reasons(doc)]
    return out


def status(ws: Workspace, gid: str, subject: str) -> dict:
    """NOT_REQUESTED | WAITING | APPROVED | CHANGES_REQUESTED | BLOCKED | INVALIDATED | OUTDATED."""
    g = gate_def(gid)
    reqs, decs = load_requests(gid, subject), load_decisions(gid, subject)
    cur = current_hashes(ws, gid, subject)
    req = reqs[-1] if reqs else None
    dec = decs[-1] if decs else None
    info = {"gate": gid, "name": g["name"], "subject": subject, "request": req,
            "decision": None, "comments": None, "stale": []}
    if req is None:
        s = "NOT_REQUESTED"
    elif dec is None or dec.get("request_n", 0) < req["n"]:
        s = "WAITING" if req["artifacts"] == cur else "OUTDATED"
    else:
        info["decision"] = dec
        info["comments"] = dec.get("comments")
        same = dec["artifacts"] == cur
        if dec["decision"] == "APPROVED":
            s = "APPROVED" if same else "INVALIDATED"
            if s == "APPROVED":
                info["stale"] = stale_in(ws, list(cur))
                if info["stale"]:
                    s = "INVALIDATED"
        elif dec["decision"] == "CHANGES_REQUESTED":
            s = "CHANGES_REQUESTED" if same else "OUTDATED"
        else:
            s = "BLOCKED" if same else "OUTDATED"
    info["status"] = s
    return info


def request(ws: Workspace, gid: str, subject: str, summary: Optional[str] = None) -> dict:
    from .validate import validate
    g = gate_def(gid)
    if not g.get("implemented"):
        raise BAError(f"{gid} {g['name']} is not available in milestone 1")
    check_subject(ws, gid, subject)
    rels = artifact_rels(gid, subject)
    missing = [r for r in rels if ws.hash_rel(r) is None]
    if missing:
        raise BAError(f"cannot request {gid}: missing " + ", ".join(paths.show(m) for m in missing))

    def covered(p: str) -> bool:
        return any(p == r or (r.endswith("/") and p.startswith(r)) for r in rels)

    errors = [i for i in validate(ws) if i.level == "ERROR" and covered(i.path)]
    if errors:
        raise BAError(f"cannot request {gid}: fix these first\n  " + "\n  ".join(str(e) for e in errors))
    stale = stale_in(ws, rels)
    if stale:
        raise BAError(f"cannot request {gid}: inputs changed since these were written — "
                      f"regenerate or re-stamp first\n  " + "\n  ".join(stale))

    cur = current_hashes(ws, gid, subject)
    with store.locked():
        f = _request_file(gid, subject)
        data = store.load_json(f) or {"gate": gid, "subject": subject, "requests": []}
        prev = data["requests"][-1] if data["requests"] else None
        if prev and prev["artifacts"] == cur:
            decs = load_decisions(gid, subject)
            if not decs or decs[-1].get("request_n", 0) < prev["n"]:
                return {"request": prev, "already_waiting": True}
        entry = {"n": (prev["n"] + 1) if prev else 1, "requested_at": store.now(),
                 "artifacts": cur, "summary": summary}
        data["requests"].append(entry)
        store.save_json(f, data)
        if prev:
            for rel in rels:
                if prev["artifacts"].get(rel) != cur[rel]:
                    for doc in ws.docs_under(rel):
                        doc.write_fm({"version": int(doc.fm.get("version") or 1) + 1})
    return {"request": entry, "already_waiting": False}


def record_decision(ws: Workspace, gid: str, subject: str, decision: str, comments: str,
                    reviewer: str, source: str) -> Path:
    """Only called from the UserPromptSubmit hook or `ba decide` on a human's terminal."""
    if decision not in ("APPROVED", "CHANGES_REQUESTED", "BLOCKED"):
        raise BAError(f"unknown decision {decision}")
    check_subject(ws, gid, subject)
    st = status(ws, gid, subject)
    req = st["request"]
    if req is None:
        raise BAError(f"No review has been requested for {gid} on {subject}, so there is nothing to decide. "
                      f"Ask Claude to continue the workflow (/ba-next).")
    if req["artifacts"] != current_hashes(ws, gid, subject):
        raise BAError(f"The artifacts for {gid} on {subject} changed after the review was requested. "
                      f"Run /ba-next so Claude re-requests the review, then decide.")
    stale = stale_in(ws, artifact_rels(gid, subject))
    if stale:
        raise BAError(f"Inputs of {gid} on {subject} changed after the review was requested:\n  "
                      + "\n  ".join(stale) + "\nRun /ba-next first.")
    if decision == "CHANGES_REQUESTED" and not (comments or "").strip():
        raise BAError("Requesting changes needs comments: /ba-changes <SUBJECT> <GATE> <what to change>")
    entry = {"gate": gid, "gate_name": gate_def(gid)["name"], "subject": subject,
             "decision": decision, "reviewer": reviewer, "decided_at": store.now(),
             "comments": (comments or "").strip() or None, "request_n": req["n"],
             "artifacts": req["artifacts"], "source": source}
    with store.locked():
        d = paths.DECISIONS / subject
        stamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        f = d / f"{gid}-{stamp}.json"
        n = 2
        while f.exists():
            f = d / f"{gid}-{stamp}-{n}.json"
            n += 1
        store.save_json(f, entry)
    return f


def instances(ws: Workspace) -> List[tuple]:
    """Every (gate, subject) pair that can exist right now."""
    out = []
    run = ws.active_run()
    for gid, g in schema.workflow()["gates"].items():
        if not g.get("implemented"):
            continue
        if g["subject"] == "RUN":
            out += [(gid, run["run_id"])] if run else []
        else:
            out += [(gid, uc) for uc in ws.backlog_ucs]
    return out
