"""`ba` command-line entry point. Run `tools/ba --help`."""
from __future__ import annotations

import argparse
import json
import sys
from typing import List, Optional

import yaml

from . import coding, compile as spec_compile, context, gates, graph, hooks, ids, paths, planning, prereview, schema, store
from .engine import GateCache, derive_run, derive_uc
from .ids import as_list, normalize_id
from .store import BAError
from .sync import run_sync, stage_status, stamp_doc, step_label, step_note
from .validate import errors_by_rel, validate
from .workspace import Workspace


# ------------------------------------------------------------------ helpers

def _derive_all(ws: Workspace):
    issues = validate(ws)
    errs = errors_by_rel(issues)
    return issues, errs, GateCache(ws)


def _scope_ucs(ws: Workspace, scope: Optional[str], run: Optional[dict]) -> Optional[List[str]]:
    if not scope:
        return None
    sid = normalize_id(scope)
    if sid in ws.epics:
        return [u.get("use_case_id") for u in as_list(ws.epics[sid].get("use_cases"))]
    if ws.catalog_of(sid) == "use-cases":
        return [sid]
    raise BAError(f"{scope} is neither an epic in the backlog nor a use case")


def _parse_data(args) -> dict:
    if getattr(args, "file", None):
        data = store.load_yaml(store.resolve_user_path(args.file))
    elif getattr(args, "data", None):
        try:
            data = yaml.safe_load(args.data)
        except yaml.YAMLError as e:
            raise BAError(f"--data is not valid JSON/YAML: {e}")
    else:
        raise BAError("give --data '<json or yaml>' or --file <path>")
    if not isinstance(data, dict):
        raise BAError("the data must be an object/mapping")
    return data


def _related_questions(ws: Workspace, subject: str, rels: List[str]) -> List[dict]:
    topics = {subject}
    for rel in rels:
        for doc in ws.docs_under(rel):
            topics |= set(as_list(doc.fm.get("open_questions")))
            for vals in (doc.fm.get("relations") or {}).values():
                topics |= set(as_list(vals))
    out = []
    for q in ws.items_in("open-questions"):
        if q.get("status") != "OPEN":
            continue
        if ws.run(subject) or q["id"] in topics or topics & set(as_list(q.get("related"))):
            out.append(q)
    return out


# ------------------------------------------------------------------ commands

def cmd_status(args) -> int:
    ws = Workspace()
    issues, errs, gs = _derive_all(ws)
    project = (ws.state.get("project") or {}).get("name", "BA workspace")
    print(f"{project} — BA workflow status")
    print()
    for run in ws.runs():
        d = derive_run(ws, run, gs, errs)
        active = " (active)" if run["run_id"] == ws.state.get("active_run") else ""
        print(f"{run['run_id']}{active}  {run['workflow_type']}  {d['status']}  phase: {d['phase']}")
        if d["next_step"]:
            print(f"  next:    {d['next_step']}")
        ra = d.get("run_action")
        if ra and ra.get("action") not in ("REQUEST_GATE", "WAIT_FOR_STAKEHOLDERS"):
            print(f"  action:  {ra['action']} {ra.get('step') or ra.get('gate')} — agent {ra.get('agent')}"
                  + (f"\n           {ra['reason']}" if ra.get("reason") else ""))
        if ra and ra.get("action") == "WAIT_FOR_STAKEHOLDERS":
            for q in ra["questions"]:
                print(f"  waiting: {q['id']} [{q.get('target_stakeholder')}] {q.get('question')}")
        if d["status"] in ("BLOCKED", "NOT_STARTED") and d["blocked_reason"]:
            print(f"  blocked: {d['blocked_reason']}")

    print("\nGates")
    shown = 0
    for gid, subj in gates.instances(ws):
        g = gs(gid, subj)
        if g["status"] == "NOT_REQUESTED" and not args.all:
            continue
        when = (g["decision"] or {}).get("decided_at") or (g["request"] or {}).get("requested_at") or ""
        print(f"  {gid}  {g['name']:<24} {subj:<8} {g['status']:<18} {when}")
        if g["status"] == "WAITING":
            print(f"          decide: /ba-approve {subj} {gid}   or   /ba-changes {subj} {gid} <comments>")
        shown += 1
    if not shown:
        print("  (none requested yet)")

    run = ws.active_run()
    stages = schema.engine()["stages"]
    for eid, epic in ws.epics.items():
        print(f"\n{eid}  {epic.get('name')}  [{epic.get('priority')}]")
        for u in as_list(epic.get("use_cases")):
            uc = u.get("use_case_id")
            r = derive_uc(ws, uc, run, gs, errs)
            st = {f: stage_status(ws, gs, uc, s, r) for f, s in stages.items()}
            later = "".join(f" {k}:{st[f]}" for f, k in (("technical_review_status", "tech"),
                                                          ("coding_status", "code"), ("testing_status", "test"),
                                                          ("documentation_status", "docs"))
                            if st.get(f) not in (None, "NOT_STARTED"))
            print(f"  {uc}  {ws.label(uc):<30} {u.get('status', ''):<11} ui:{st['ui_status']:<18} "
                  f"spec:{st['spec_status']:<18}{later} → {step_label(r)}: {step_note(r)}")

    stale = [(d.rel, ws.stale_reasons(d)) for d in ws.docs.values() if ws.stale_reasons(d)]
    print("\nStale artifacts: " + ("none" if not stale else ""))
    for rel, reasons in stale:
        print(f"  ba-ai/{rel}: {'; '.join(reasons)}")
    n_err = sum(1 for i in issues if i.level == "ERROR")
    n_warn = sum(1 for i in issues if i.level == "WARN")
    print(f"Validation: {n_err} errors, {n_warn} warnings" + ("  (tools/ba validate)" if n_err or n_warn else ""))
    open_q = [q["id"] for q in ws.items_in("open-questions") if q.get("status") == "OPEN"]
    print(f"Open questions: {len(open_q)}" + (f" ({', '.join(open_q)})" if open_q else ""))
    if coding.authorized(ws):
        print("Coding authorized for: " + ", ".join(coding.authorized(ws)))
    return 0


def cmd_next(args) -> int:
    ws = Workspace()
    issues, errs, gs = _derive_all(ws)
    run = ws.active_run()
    if not run:
        raise BAError("no active run in workflow/state.json")
    d = derive_run(ws, run, gs, errs)
    scope = _scope_ucs(ws, args.scope, run)
    results = d["use_cases"]
    if scope is not None:
        results = {uc: results.get(uc) or derive_uc(ws, uc, run, gs, errs) for uc in scope}
    ordered = [results[uc] for uc in ws.by_priority(list(results))]
    if args.json:
        out = {k: v for k, v in d.items() if k != "use_cases"}
        out["use_cases"] = ordered
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        return 0
    print(f"{d['run_id']}  {d['workflow_type']}  phase: {d['phase']}  status: {d['status']}")
    if d["run_action"]:
        ra = d["run_action"]
        if ra["action"] in ("REQUEST_GATE", "REVISE"):
            print(f"\nRUN ACTION  {ra['action']} {ra['gate']} on {ra['subject']}"
                  + (f"  agent={ra['agent']}" if ra.get("agent") else "")
                  + (f"\n  comments: {ra['comments']}" if ra.get("comments") else ""))
        elif ra["action"] == "PRE_REVIEW":
            print(f"\nRUN ACTION  PRE_REVIEW {ra['gate']} on {ra['subject']} (round {ra['round']})  agent=review-agent"
                  f"\n  brief: {ra['brief_command']}")
        elif ra["action"] == "WAIT_FOR_STAKEHOLDERS":
            print("\nWAITING FOR STAKEHOLDERS (master §8 step 2.5)")
            for q in ra["questions"]:
                print(f"  {q['id']} [{q.get('target_stakeholder')}, {q.get('priority')}] {q.get('question')}")
        else:
            print(f"\nRUN ACTION  {ra['action']} {ra['step']} ({ra['step_name']})  agent={ra['agent']}"
                  f"\n  context: {ra['context_command']}\n  reason: {ra['reason']}")
    if d["status"] in ("BLOCKED", "NOT_STARTED") and not ordered and d["blocked_reason"]:
        print(f"\n{d['status']}  {d['blocked_reason']}")
    groups = {"ACTION": [], "WAITING": [], "NEEDS_HUMAN": [], "BLOCKED": [], "NOT_READY": [], "DONE": []}
    for r in ordered:
        groups[r["state"]].append(r)
    for state, title in (("ACTION", "ACTIONS"), ("WAITING", "WAITING FOR HUMAN"),
                         ("NEEDS_HUMAN", "NEEDS A HUMAN DECISION"), ("BLOCKED", "BLOCKED"),
                         ("NOT_READY", "NOT READY"), ("DONE", "DONE")):
        if not groups[state]:
            continue
        print(f"\n{title}")
        for r in groups[state]:
            if state == "ACTION" and r["action"] == "REQUEST_GATE":
                print(f"  {r['uc']}  {r['gate']}  REQUEST_GATE  (orchestrator: tools/ba gate request {r['gate']} {r['uc']})")
                if r.get("pre_review_findings"):
                    print(f"        AI pre-review findings left for the human: {r['pre_review_findings']}")
            elif state == "ACTION" and r["action"] == "PRE_REVIEW":
                print(f"  {r['uc']}  {r['gate']}  PRE_REVIEW  round {r['round']}  agent=review-agent"
                      f"  (brief: {r['brief_command']})")
            elif state == "ACTION":
                who = r["agent"] or "/".join(r.get("agents", []))
                print(f"  {r['uc']}  {r['step']}  {r['action']:<10} steps {','.join(r['steps'])}  agent={who}")
                if r.get("pre_command"):
                    print(f"        first: {r['pre_command']}")
                if r.get("reason"):
                    print(f"        reason: {r['reason']}")
                if r.get("comments"):
                    print(f"        reviewer comments ({r.get('comments_gate')}): {r['comments']}")
            elif state == "WAITING":
                print(f"  {r['uc']}  {r['gate']}  requested {r['requested_at']}")
            elif state == "DONE":
                print(f"  {r['uc']}  delivered")
            else:
                print(f"  {r['uc']}  {r['reason']}")
    return 0


def cmd_context(args) -> int:
    if schema.run_step(args.use_case.strip().upper()):
        out, missing = context.build_run(args.use_case)
    else:
        out, missing = context.build(args.use_case)
    print(f"context package: {out}")
    if missing:
        print("MISSING INPUT — stop and report:")
        for m in missing:
            print(f"  - {m}")
        return 3
    return 0


def cmd_stamp(args) -> int:
    with store.locked():
        for arg in args.paths:
            p = store.resolve_user_path(arg)
            if p.is_dir():
                p = p / "README.md"
            ws = Workspace()
            doc = ws.docs.get(paths.rel(p))
            if not doc:
                raise BAError(f"{arg} is not a BA document (needs frontmatter with artifact_type)")
            entries = stamp_doc(ws, doc)
            print(f"stamped ba-ai/{doc.rel} ({len(entries)} inputs)")
    return 0


def cmd_validate(args) -> int:
    ws = Workspace()
    only = None
    if args.paths:
        only = set()
        for arg in args.paths:
            rel = paths.rel(store.resolve_user_path(arg))
            only.add(rel)
            only |= {d.rel for d in ws.docs_under(rel.rstrip("/") + "/")}
    issues = validate(ws, only)
    for i in issues:
        print(i)
    n_err = sum(1 for i in issues if i.level == "ERROR")
    n_warn = len(issues) - n_err
    print(("FAILED" if n_err else "OK") + f" — {n_err} errors, {n_warn} warnings")
    return 1 if n_err else 0


def cmd_gate_request(args) -> int:
    ws = Workspace()
    gid, subject = normalize_id(args.gate), normalize_id(args.subject)
    pr = prereview.state(ws, gid, subject, gates.status(ws, gid, subject))
    if pr["status"] != "OK" and not args.skip_pre_review:
        what = ("run the AI pre-review first (review-agent; `tools/ba prereview brief`)" if pr["status"] == "NEEDED"
                else "address the AI pre-review findings, or record why they stay (`tools/ba prereview resolve`)")
        raise BAError(f"{gid} on {subject} needs its AI pre-review (D-40): {what}. "
                      f"Only on the BA's instruction: --skip-pre-review")
    res = gates.request(ws, gid, subject, args.summary)
    g = gates.gate_def(gid)
    req = res["request"]
    label = f" {ws.label(subject)}" if ws.label(subject) else ""
    print(("Already waiting: " if res["already_waiting"] else "Review requested: ")
          + f"{gid} {g['name']} for {subject}{label} (request #{req['n']})")
    print(f"Reviewer: {g.get('reviewer')}")
    print("\nArtifacts under review:")
    for rel in req["artifacts"]:
        print(f"  ba-ai/{rel}")
    if g.get("review_focus"):
        print("\nWhat to check:")
        for f in g["review_focus"]:
            print(f"  - {f}")
    if pr.get("carried"):
        print("\nAI pre-review findings not applied (decide whether they matter):")
        for f in pr["carried"]:
            print(f"  [{f['severity']}] ba-ai/{f['artifact']}: {f['issue']}")
        if pr.get("resolved_note"):
            print(f"  owner's reason: {pr['resolved_note']}")
    qs = _related_questions(ws, subject, list(req["artifacts"]))
    if qs:
        print("\nOpen questions to be aware of:")
        for q in qs:
            print(f"  {q['id']} [{q.get('priority')}] {q.get('question')}")
    print("\nTo decide, the reviewer types:")
    print(f"  /ba-approve {subject} {gid} [comment]")
    print(f"  /ba-changes {subject} {gid} <what to change>")
    run_sync()
    return 0


def cmd_gate_status(args) -> int:
    ws = Workspace()
    gs = GateCache(ws)
    subject = normalize_id(args.subject) if args.subject else None
    rows = [gs(g, s) for g, s in gates.instances(ws) if subject in (None, s)]
    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False, default=str))
        return 0
    for r in rows:
        if r["status"] == "NOT_REQUESTED" and not subject:
            continue
        print(f"{r['gate']}  {r['name']:<24} {r['subject']:<8} {r['status']}")
        if r["decision"]:
            dec = r["decision"]
            print(f"    last decision: {dec['decision']} by {dec['reviewer']} at {dec['decided_at']}"
                  + (f" — {dec['comments']}" if dec.get("comments") else ""))
        for s in r["stale"]:
            print(f"    stale: {s}")
    return 0


def cmd_decide(args) -> int:
    """Fallback for humans when the hook is unavailable. Refuses to run without a terminal."""
    if not sys.stdin.isatty():
        raise BAError("`ba decide` must be run by a person in their own terminal, not by Claude.")
    decision = {"approve": "APPROVED", "changes": "CHANGES_REQUESTED", "block": "BLOCKED"}[args.decision]
    gid, subject = normalize_id(args.gate), normalize_id(args.subject)
    comments = " ".join(args.comments)
    answer = input(f"Record {decision} for {gid} on {subject}? Type the subject ID to confirm: ").strip()
    if normalize_id(answer) != subject:
        raise BAError("not confirmed — nothing recorded")
    f = gates.record_decision(Workspace(), gid, subject, decision, comments, hooks.reviewer_name(),
                              "ba decide (terminal)")
    print(f"recorded → ba-ai/{paths.rel(f)}")
    run_sync()
    return 0


def cmd_sync(args) -> int:
    c = run_sync()
    print(f"synced: {c['docs']} documents, {c['catalogs']} catalogs updated; backlog "
          f"{'updated' if c['backlog'] else 'unchanged'}; state {'updated' if c['state'] else 'unchanged'}; "
          f"graph {'rebuilt' if c['graph'] else 'unchanged'}; {c['views']} views updated; validation {c['errors']} errors, {c['warnings']} warnings")
    return 0


def cmd_graph(args) -> int:
    if args.action == "build":
        changed = graph.save(Workspace())
        print("graph rebuilt" if changed else "graph unchanged")
        return 0
    g = store.load_json(paths.GRAPH) or graph.build(Workspace())
    for line in graph.neighborhood(g, normalize_id(args.id), args.depth):
        print(line)
    return 0


def cmd_next_id(args) -> int:
    print(ids.next_id(args.prefix))
    return 0


def cmd_find(args) -> int:
    hits = ids.find(Workspace(), " ".join(args.text))
    for score, iid, cat, name in hits[:25]:
        print(f"{iid:<14} {cat:<18} {name}")
    if not hits:
        print("no matches")
    return 0


def cmd_catalog(args) -> int:
    if args.action == "add":
        print(ids.catalog_add(args.catalog, _parse_data(args), args.force_gated))
    elif args.action == "update":
        print(ids.catalog_update(args.id, _parse_data(args), args.force_gated))
    elif args.action == "init":
        print(ids.catalog_init(args.catalog))
    elif args.action == "get":
        ws = Workspace()
        item = ws.item(normalize_id(args.id))
        if item is None:
            raise BAError(f"{args.id} not found")
        print(store.dump_yaml(item), end="")
    elif args.action == "list":
        ws = Workspace()
        for item in ws.items_in(args.catalog):
            print(f"{item['id']:<10} {ws.label(item['id'])}")
    return 0


def cmd_state(args) -> int:
    if args.action == "show":
        print(json.dumps(store.load_json(paths.STATE), indent=2, ensure_ascii=False))
        return 0
    with store.locked():
        state = store.load_json(paths.STATE)
        rid = normalize_id(args.run)
        run = next((r for r in state.get("runs", []) if r.get("run_id") == rid), None)
        if not run:
            raise BAError(f"no run {rid}")
        run["manual_block"] = args.action == "block"
        run["blocked_reason"] = " ".join(args.reason) if args.action == "block" else None
        run["updated_at"] = state["updated_at"] = store.now()
        store.save_json(paths.STATE, state)
    run_sync()
    print(f"{rid} {'blocked' if args.action == 'block' else 'unblocked'}")
    return 0


def cmd_backlog(args) -> int:
    res = planning.apply_plan(_parse_data(args))
    print(f"backlog planned: {len(res['epics'])} epics ({', '.join(res['epics'])}), {res['use_cases']} use cases"
          + (f"; removed from the backlog: {', '.join(res['dropped'])}" if res["dropped"] else ""))
    run_sync()
    return 0


def cmd_coding(args) -> int:
    if args.action == "authorize":
        res = coding.authorize(args.use_case)
        print(f"coding authorized for {res['use_case']} (now: {', '.join(res['authorized'])})")
        for r in res["repositories"]:
            print(f"  {r['id']} {r['name']}: {r['path']}" + ("" if r["exists"] else "  (does not exist yet)"))
    elif args.action == "revoke":
        left = coding.revoke(args.use_case)
        print("coding authorization " + (f"now: {', '.join(left)}" if left else "cleared"))
    else:
        ws = Workspace()
        gs = GateCache(ws)
        ucs = coding.authorized(ws)
        print("authorized: " + (", ".join(ucs) if ucs else "none"))
        for uc in ([normalize_id(args.use_case)] if args.use_case else ucs):
            probs = coding.problems(ws, gs, uc)
            print(f"  {uc}: " + ("gates OK" if not probs else "; ".join(probs)))
    return 0


def cmd_qa(args) -> int:
    uc = normalize_id(args.use_case)
    with store.locked():
        ws = Workspace()
        doc = ws.docs.get(ws.doc_rel("test-results", uc))
        if not doc:
            raise BAError(f"{uc} has no test results yet — nothing to retest")
        doc.write_fm({"retest_requested_at": store.now()})
    print(f"retest requested for {uc}; /ba-next runs the tests again")
    run_sync()
    return 0


def cmd_compile(args) -> int:
    res = spec_compile.compile_spec(args.use_case)
    print(f"compiled {res['path']}")
    if res["narrative_todo"]:
        print("narrative sections to write (spec-agent): " + "; ".join(res["narrative_todo"]))
    return 0


def cmd_prereview(args) -> int:
    if args.action == "brief":
        print(f"pre-review brief: {prereview.brief(args.gate, args.subject)}")
    elif args.action == "record":
        findings = []
        if args.file:
            data = store.load_yaml(store.resolve_user_path(args.file))
            findings = data.get("findings", data) if isinstance(data, dict) else data
        e = prereview.record(args.gate, args.subject, args.verdict, findings)
        print(f"pre-review #{e['n']} recorded: {e['verdict']} ({len(e['findings'])} findings)")
        run_sync()
    elif args.action == "resolve":
        prereview.resolve(args.gate, args.subject, args.note)
        print("findings kept as they are, with the reason; the gate can be requested")
        run_sync()
    else:
        ws = Workspace()
        gid, subject = normalize_id(args.gate), normalize_id(args.subject)
        st = prereview.state(ws, gid, subject, gates.status(ws, gid, subject))
        print(f"{gid} {subject}: {st['status']}" + (f" (round {st.get('round')})" if st.get("round") else ""))
        for f in st.get("findings") or st.get("carried") or []:
            print(f"  [{f['severity']}] ba-ai/{f['artifact']}: {f['issue']}")
    return 0


def cmd_hook(args) -> int:
    return hooks.user_prompt_submit() if args.event == "user-prompt" else hooks.pre_tool_use()


# ------------------------------------------------------------------ parser

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tools/ba", description="BA workflow bookkeeping (addendum D-04).")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", help="runs, gates, backlog, stale artifacts")
    s.add_argument("--all", action="store_true", help="also list gates not requested yet")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("next", help="what the orchestrator should do next")
    s.add_argument("scope", nargs="?", help="UC-ID or EPIC-ID")
    s.add_argument("--json", action="store_true")
    s.set_defaults(func=cmd_next)

    s = sub.add_parser("context", help="build the context package for a use case (Step 5.1) or a run step")
    s.add_argument("use_case", help="UC-ID, or a run step: " + ", ".join(schema.run_steps()))
    s.set_defaults(func=cmd_context)

    s = sub.add_parser("stamp", help="record the inputs a document was built from")
    s.add_argument("paths", nargs="+")
    s.set_defaults(func=cmd_stamp)

    s = sub.add_parser("validate", help="check artifacts against their schemas")
    s.add_argument("paths", nargs="*")
    s.set_defaults(func=cmd_validate)

    s = sub.add_parser("gate", help="request a review or show gate status")
    gsub = s.add_subparsers(dest="gate_cmd", required=True)
    r = gsub.add_parser("request")
    r.add_argument("gate")
    r.add_argument("subject")
    r.add_argument("--summary")
    r.add_argument("--skip-pre-review", action="store_true",
                   help="request without the AI pre-review (BA instruction only)")
    r.set_defaults(func=cmd_gate_request)
    r = gsub.add_parser("status")
    r.add_argument("subject", nargs="?")
    r.add_argument("--json", action="store_true")
    r.set_defaults(func=cmd_gate_status)

    s = sub.add_parser("decide", help="(humans only, in a terminal) record a gate decision")
    s.add_argument("decision", choices=["approve", "changes", "block"])
    s.add_argument("subject")
    s.add_argument("gate")
    s.add_argument("comments", nargs="*")
    s.set_defaults(func=cmd_decide)

    s = sub.add_parser("sync", help="recompute statuses, backlog, state and graph")
    s.set_defaults(func=cmd_sync)

    s = sub.add_parser("graph", help="build or explore the knowledge graph")
    gsub = s.add_subparsers(dest="action", required=True)
    gsub.add_parser("build")
    r = gsub.add_parser("show")
    r.add_argument("id")
    r.add_argument("--depth", type=int, default=2)
    s.set_defaults(func=cmd_graph)

    s = sub.add_parser("next-id", help="allocate the next ID for a prefix")
    s.add_argument("prefix")
    s.set_defaults(func=cmd_next_id)

    s = sub.add_parser("find", help="search existing catalog items (reuse before creating)")
    s.add_argument("text", nargs="+")
    s.set_defaults(func=cmd_find)

    s = sub.add_parser("catalog", help="add, update or read catalog items")
    csub = s.add_subparsers(dest="action", required=True)
    for name in ("add", "update"):
        r = csub.add_parser(name)
        r.add_argument("catalog" if name == "add" else "id")
        r.add_argument("--data")
        r.add_argument("--file")
        r.add_argument("--force-gated", action="store_true",
                       help="allow editing a catalog under an APPROVED run gate (BA instruction only)")
    csub.add_parser("init", help="create an empty catalog (e.g. a product with no integrations)").add_argument("catalog")
    csub.add_parser("get").add_argument("id")
    csub.add_parser("list").add_argument("catalog")
    s.set_defaults(func=cmd_catalog)

    s = sub.add_parser("state", help="show state, or block/unblock a run manually")
    ssub = s.add_subparsers(dest="action", required=True)
    ssub.add_parser("show")
    r = ssub.add_parser("block")
    r.add_argument("run")
    r.add_argument("reason", nargs="+")
    ssub.add_parser("unblock").add_argument("run")
    s.set_defaults(func=cmd_state)

    s = sub.add_parser("backlog", help="write the delivery backlog from a plan (Phase 4)")
    bsub = s.add_subparsers(dest="action", required=True)
    r = bsub.add_parser("plan")
    r.add_argument("--data")
    r.add_argument("--file")
    s.set_defaults(func=cmd_backlog)

    s = sub.add_parser("coding", help="coding authorization for product repositories (D-13)")
    csub = s.add_subparsers(dest="action", required=True)
    csub.add_parser("authorize").add_argument("use_case")
    csub.add_parser("revoke").add_argument("use_case", nargs="?")
    csub.add_parser("status").add_argument("use_case", nargs="?")
    s.set_defaults(func=cmd_coding)

    s = sub.add_parser("qa", help="QA helpers (Phase 8)")
    qsub = s.add_subparsers(dest="action", required=True)
    qsub.add_parser("retest", help="run a use case's tests again after a human fixed the cause").add_argument("use_case")
    s.set_defaults(func=cmd_qa)

    s = sub.add_parser("compile", help="assemble the use-case specification from its upstream artifacts (5.8)")
    s.add_argument("use_case")
    s.set_defaults(func=cmd_compile)

    s = sub.add_parser("prereview", help="AI pre-review before a human gate (D-40)")
    psub = s.add_subparsers(dest="action", required=True)
    for name in ("brief", "status"):
        r = psub.add_parser(name)
        r.add_argument("gate")
        r.add_argument("subject")
    r = psub.add_parser("record")
    r.add_argument("gate")
    r.add_argument("subject")
    r.add_argument("--verdict", required=True, choices=["PASS", "FINDINGS", "pass", "findings"])
    r.add_argument("--file", help="YAML list of findings: artifact, severity (MAJOR|MINOR), issue, suggestion")
    r = psub.add_parser("resolve")
    r.add_argument("gate")
    r.add_argument("subject")
    r.add_argument("--note", required=True)
    s.set_defaults(func=cmd_prereview)

    s = sub.add_parser("hook", help="Claude Code hook entry points")
    s.add_argument("event", choices=["user-prompt", "pre-tool-use"])
    s.set_defaults(func=cmd_hook)
    return p


def main(argv: Optional[List[str]] = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        rc = args.func(args) or 0
    except BAError as e:
        print(f"ba: {e}", file=sys.stderr)
        rc = 1
    sys.exit(rc)
