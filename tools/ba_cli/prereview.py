"""AI pre-review before a human gate (addendum D-40).

A reviewer agent with a fresh context checks a gate's artifacts against their inputs, the method-skill
checklists and the gate's review focus, *before* the human is asked. Its verdict is recorded with the
content hashes it saw, exactly like a gate request, so a pre-review is valid only for that content.

This is never a gate decision: it lives in reviews/pre-review/, and humans still decide every gate.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Callable, List, Optional

from . import gates, paths, schema, store
from .ids import as_list, normalize_id
from .store import BAError

DIR = paths.BA / "reviews" / "pre-review"
VERDICTS = ("PASS", "FINDINGS")
SEVERITIES = ("MAJOR", "MINOR")


def _file(gid: str, subject: str) -> Path:
    return DIR / subject / f"{gid}.json"


def entries(gid: str, subject: str) -> List[dict]:
    return (store.load_json(_file(gid, subject)) or {}).get("reviews", [])


def max_rounds() -> int:
    return int((schema.workflow().get("pre_review") or {}).get("max_rounds", 2))


def required(gid: str) -> bool:
    return bool((schema.gate(gid) or {}).get("pre_review"))


def _request_n(g: dict) -> int:
    return int((g.get("request") or {}).get("n") or 0)


def state(ws, gid: str, subject: str, g: dict) -> dict:
    """Where the pre-review of a gate that is about to be requested stands.

    status: OK (request the gate) | NEEDED (run the reviewer) | FINDINGS (owner must fix or resolve).
    `g` is the gate status (from gates.status or the engine's cache); rounds count from its last request.
    """
    if not required(gid):
        return {"status": "OK", "carried": []}
    req_n = _request_n(g)
    rounds = [e for e in entries(gid, subject) if e.get("after_request") == req_n]
    cur = gates.current_hashes(ws, gid, subject)
    last = rounds[-1] if rounds else None
    carried = ((last or {}).get("findings") or []) if (last or {}).get("verdict") == "FINDINGS" else []
    if last and last["artifacts"] == cur:
        if last["verdict"] == "PASS":
            return {"status": "OK", "carried": [], "round": len(rounds)}
        if last.get("resolved_note") or len(rounds) >= max_rounds():
            return {"status": "OK", "carried": carried, "round": len(rounds),
                    "resolved_note": last.get("resolved_note")}
        return {"status": "FINDINGS", "findings": last["findings"], "round": len(rounds)}
    if len(rounds) >= max_rounds():
        return {"status": "OK", "carried": carried, "round": len(rounds)}
    return {"status": "NEEDED", "round": len(rounds) + 1}


def _gate_status(ws, gid: str, subject: str) -> dict:
    return gates.status(ws, gid, subject)


def brief(gid_arg: str, subject_arg: str) -> str:
    """Write the reviewer's brief: what to check, which artifacts, their inputs and their method skills."""
    from .workspace import Workspace
    gid, subject = normalize_id(gid_arg), normalize_id(subject_arg)
    ws = Workspace()
    g = gates.gate_def(gid)
    gates.check_subject(ws, gid, subject)
    rels = gates.artifact_rels(gid, subject)
    arts = []
    for rel in rels:
        docs = ws.docs_under(rel)
        inputs = sorted({e.get("path") or e.get("ref") for d in docs for e in as_list(d.fm.get("built_from"))
                         if isinstance(e, dict)} - {None})
        skills: List[str] = []
        if g["subject"] == "USE_CASE":
            step = next((s for s in schema.engine_steps()
                         if ws.doc_rel(s["artifact_type"], subject) in [rel] + [d.rel for d in docs]), None)
            skills = (step or {}).get("skills", [])
        else:
            out = schema.run_output_for(rel)
            if out:
                skills = (schema.run_step(out["step"]) or {}).get("skills", [])
            else:   # a catalog: the run step that fills it
                skills = next((sd.get("skills", []) for sd in schema.run_steps().values()
                               if schema.catalog_for_path(rel) in (sd.get("catalogs") or [])), [])
        arts.append({"artifact": paths.show(rel), "exists": ws.hash_rel(rel) is not None,
                     "built_from": inputs, "method_skills": [f".claude/skills/{s}/SKILL.md" for s in skills]})
    st = state(ws, gid, subject, _gate_status(ws, gid, subject))
    prev = entries(gid, subject)
    pkg = {
        "task": f"AI pre-review of {gid} {g['name']} for {subject} {ws.label(subject)}".rstrip(),
        "generated_at": store.now(),
        "gate": gid, "subject": subject, "human_reviewer": g.get("reviewer"),
        "review_focus": g.get("review_focus", []),
        "artifacts": arts,
        "round": st.get("round"), "max_rounds": max_rounds(),
        "previous_findings": (prev[-1].get("findings") if prev else []) or [],
        "context_package": (f"ba-ai/workflow/context/{subject}.yaml" if g["subject"] == "USE_CASE" else None),
        "record_with": f"tools/ba prereview record {gid} {subject} --verdict PASS|FINDINGS --file <findings.yaml>",
    }
    out = paths.CONTEXT_DIR / f"{subject}-{gid}-prereview.yaml"
    store.save_yaml(out, pkg)
    return paths.show(paths.rel(out))


def _check_findings(rels: List[str], findings) -> List[dict]:
    if not isinstance(findings, list):
        raise BAError("findings must be a list")
    out = []
    for f in findings:
        if not isinstance(f, dict) or not f.get("issue"):
            raise BAError(f"every finding needs an 'issue' ({f!r:.60})")
        art = str(f.get("artifact") or "").replace("ba-ai/", "", 1)
        if not any(art == r or (r.endswith("/") and art.startswith(r)) or art == r.rstrip("/") for r in rels):
            raise BAError(f"finding artifact {f.get('artifact')!r} is not one of the gate's artifacts: "
                          + ", ".join(paths.show(r) for r in rels))
        sev = str(f.get("severity") or "MAJOR").upper()
        if sev not in SEVERITIES:
            raise BAError(f"severity must be one of {SEVERITIES}")
        out.append({"artifact": art, "severity": sev, "issue": f["issue"],
                    **({"suggestion": f["suggestion"]} if f.get("suggestion") else {})})
    return out


def record(gid_arg: str, subject_arg: str, verdict: str, findings) -> dict:
    from .workspace import Workspace
    gid, subject = normalize_id(gid_arg), normalize_id(subject_arg)
    verdict = verdict.upper()
    if verdict not in VERDICTS:
        raise BAError(f"verdict must be one of {VERDICTS}")
    with store.locked():
        ws = Workspace()
        gates.check_subject(ws, gid, subject)
        rels = gates.artifact_rels(gid, subject)
        missing = [r for r in rels if ws.hash_rel(r) is None]
        if missing:
            raise BAError("cannot pre-review: missing " + ", ".join(paths.show(m) for m in missing))
        fs = _check_findings(rels, findings or [])
        if verdict == "FINDINGS" and not fs:
            raise BAError("verdict FINDINGS needs at least one finding")
        if verdict == "PASS":
            fs = [f for f in fs if f["severity"] == "MINOR"]          # minor notes may travel with a PASS
        g = _gate_status(ws, gid, subject)
        data = store.load_json(_file(gid, subject)) or {"gate": gid, "subject": subject, "reviews": []}
        entry = {"n": len(data["reviews"]) + 1, "reviewed_at": store.now(), "after_request": _request_n(g),
                 "artifacts": gates.current_hashes(ws, gid, subject), "verdict": verdict, "findings": fs}
        data["reviews"].append(entry)
        store.save_json(_file(gid, subject), data)
    return entry


def resolve(gid_arg: str, subject_arg: str, note: str) -> dict:
    """The owner keeps the artifact as it is and says why; the gate can then be requested."""
    from .workspace import Workspace
    gid, subject = normalize_id(gid_arg), normalize_id(subject_arg)
    if not (note or "").strip():
        raise BAError("give the reason the findings are not applied: --note '...'")
    with store.locked():
        ws = Workspace()
        data = store.load_json(_file(gid, subject)) or {}
        last = (data.get("reviews") or [None])[-1]
        if not last or last["verdict"] != "FINDINGS":
            raise BAError(f"{gid} on {subject} has no open pre-review findings")
        if last["artifacts"] != gates.current_hashes(ws, gid, subject):
            raise BAError("the artifacts changed since that pre-review — it is outdated; run a new pre-review")
        last["resolved_note"] = note.strip()
        last["resolved_at"] = store.now()
        store.save_json(_file(gid, subject), data)
    return last


def owner_steps(ws, gid: str, subject: str, findings: List[dict], steps: List[dict]) -> List[dict]:
    """Use-case steps whose artifacts the findings target, in step order."""
    hit = []
    for st in steps:
        if not st.get("artifact_type"):
            continue
        rel = ws.doc_rel(st["artifact_type"], subject)
        irel = ws.input_rel(st["artifact_type"], subject)
        if any(f["artifact"] in (rel, irel, irel.rstrip("/")) or f["artifact"].startswith(irel) for f in findings):
            hit.append(st)
    return hit


def format_findings(findings: List[dict]) -> str:
    return "; ".join(f"[{f['severity']}] ba-ai/{f['artifact']}: {f['issue']}"
                     + (f" (suggestion: {f['suggestion']})" if f.get("suggestion") else "") for f in findings)
