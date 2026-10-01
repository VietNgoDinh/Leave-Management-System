"""MODE_B end-to-end derivation tests on a throw-away fixture workspace.

Run:  .venv/bin/python -m unittest discover -s tools/tests -v      (from the workspace root)

Gate decisions are never written: a stub stands in for gates.status, so the tests only exercise
how `tools/ba` derives the next action from artifacts + gate states (master §40). AI pre-reviews
(D-40) are recorded through the real `prereview.record`, which is not a gate decision.
"""
from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[2]
FIXTURE = Path(tempfile.mkdtemp(prefix="ba-mode-b-"))
REPOS = Path(tempfile.mkdtemp(prefix="ba-repos-")).resolve()       # product repositories live outside the kit
atexit.register(shutil.rmtree, str(FIXTURE), True)
atexit.register(shutil.rmtree, str(REPOS), True)
os.environ["BA_ROOT"] = str(FIXTURE)
sys.path.insert(0, str(KIT / "tools"))

from ba_cli import coding, compile as spec_compile, engine, ids, paths, planning, prereview, schema, store, sync  # noqa: E402
from ba_cli.validate import errors_by_rel, validate  # noqa: E402
from ba_cli.workspace import Workspace  # noqa: E402

UC = "UC-001"


class Gates:
    """Stub for gates.status: every gate NOT_REQUESTED unless set."""

    def __init__(self, **st):
        self.st = {}
        for k, v in st.items():
            self.set(k, v)

    def set(self, key: str, status: str, comments: str = None):
        gid, subject = key.split("@") if "@" in key else (key, None)
        self.st[(gid.replace("_", "-"), subject)] = (status, comments)
        return self

    def __call__(self, gid, subject):
        status, comments = self.st.get((gid, subject)) or self.st.get((gid, None)) or ("NOT_REQUESTED", None)
        dec = None
        if status in ("APPROVED", "CHANGES_REQUESTED", "BLOCKED"):
            dec = {"decision": status, "comments": comments, "reviewer": "test"}
        req = None if status == "NOT_REQUESTED" else {"n": 1, "requested_at": "2026-10-02T00:00:00Z"}
        return {"gate": gid, "subject": subject, "status": status, "comments": comments, "decision": dec,
                "request": req, "stale": []}


def write(rel: str, text: str) -> Path:
    p = paths.BA / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def doc(rel: str, did: str, atype: str, headings, body: str = "", **fm) -> Path:
    front = {"id": did, "artifact_type": atype, "title": f"{did} {atype}", "status": "DRAFT", "version": 1,
             "baseline": "TO_BE", "origin": "FIXTURE", "updated_at": "", **fm}
    text = "".join(f"## {h}\n\nText.\n\n" for h in headings)
    return write(rel, "---\n" + store.dump_yaml(front) + "---\n# " + did + "\n\n" + text + body)


def add(cname: str, **data) -> str:
    return ids.catalog_add(cname, data, force_gated=True)


def derive(gs=None, validate_docs=True):
    ws = Workspace()
    errs = errors_by_rel(validate(ws)) if validate_docs else {}
    return ws, engine.derive_run(ws, ws.active_run(), gs or Gates(), errs)


def heads(atype):
    return schema.artifact_type(atype)["headings"]


def passed(gid, subject=UC):
    """The AI reviewer found nothing (D-40)."""
    prereview.record(gid, subject, "PASS", [])


class ModeBTest(unittest.TestCase):
    def setUp(self):
        for d in (FIXTURE, REPOS):
            if d.exists():
                shutil.rmtree(d)
        REPOS.mkdir()
        (FIXTURE / "tools").mkdir(parents=True)
        shutil.copytree(KIT / "tools" / "schemas", FIXTURE / "tools" / "schemas")
        (paths.BA / "workflow").mkdir(parents=True)
        shutil.copy(KIT / "ba-ai" / "workflow" / "workflow.yaml", paths.BA / "workflow" / "workflow.yaml")
        store.save_json(paths.STATE, {"schema_version": 1, "project": {"name": "Fixture"}, "active_run": "RUN-001",
                                      "runs": [{"run_id": "RUN-001", "workflow_type": "MODE_B", "status": "NOT_STARTED",
                                                "scope": {"epic": None, "use_cases": []}}],
                                      "coding_authorization": None})
        for d in ("requirements/raw", "requirements/meetings"):
            (paths.BA / d).mkdir(parents=True)
            (paths.BA / d / ".gitkeep").write_text("")

    # ------------------------------------------------------------ fixture builders

    def elicitation(self):
        write("requirements/raw/brief.md", "Stakeholders want a way to book meeting rooms.\n")
        doc("requirements/elicitation/elicitation-summary.md", "ELICITATION", "elicitation-summary",
            heads("elicitation-summary"))
        add("requirements", name="Book a room", description="Employees book rooms.", source="brief.md",
            priority="HIGH")
        sync.stamp_doc(Workspace(), Workspace().docs["requirements/elicitation/elicitation-summary.md"])

    def overview(self):
        doc("overview/product-overview.md", "PRODUCT", "product-overview", heads("product-overview"))
        act = add("actors", name="Employee", type="HUMAN", description="Books rooms")
        app = add("applications", name="Room app", type="WEB", description="Web app", actors=[act],
                  information_architecture="REQUIRED")
        ent = add("entities", name="Booking", description="A booking", owner="Room app",
                  attributes=[{"name": "id", "type": "identifier"}],
                  lifecycle={"states": ["REQUESTED", "CONFIRMED"],
                             "transitions": ["(new) -> REQUESTED: employee books",
                                             {"from": "REQUESTED", "to": "CONFIRMED", "event": "system confirms"}]})
        bp = add("business-processes", name="Booking", objective="Book rooms", actors=[act], trigger="Need a room",
                 steps=[{"name": "Book"}])
        br = add("business-rules", name="No overlap", description="Bookings may not overlap.", source="brief.md",
                 related_entities=[ent])
        uc = add("use-cases", name="Book a room", business_process=bp, actor=act, application=app,
                 description="Employee books a room.", complexity="LOW", risk_level="LOW",
                 business_rules=[br], entities_written=[ent])
        sync.stamp_doc(Workspace(), Workspace().docs["overview/product-overview.md"])
        ids.catalog_init("integrations")              # this product has no integrations
        return uc

    def baseline(self):
        for rel, atype, did in (("technical/architecture/architecture.md", "technical-architecture", "ARCH"),
                                ("technical/coding-rules/frontend.md", "coding-rules", "CODING-FRONTEND"),
                                ("technical/coding-rules/backend.md", "coding-rules", "CODING-BACKEND"),
                                ("technical/security/security-rules.md", "security-rules", "SECURITY"),
                                ("ui/design-system.md", "design-system", "DESIGN-SYSTEM")):
            doc(rel, did, atype, heads(atype))
        repo = add("repositories", name="room-api", type="backend", status="PLANNED", path=str(REPOS / "room-api"))
        add("services", name="Booking service", responsibility="Bookings", repository=repo)
        for rel in ("technical/architecture/architecture.md", "technical/coding-rules/frontend.md",
                    "technical/coding-rules/backend.md", "technical/security/security-rules.md",
                    "ui/design-system.md"):
            sync.stamp_doc(Workspace(), Workspace().docs[rel])

    def plan(self, status="READY"):
        return planning.apply_plan({"epics": [{"name": "Booking", "priority": "HIGH", "use_cases": [
            {"use_case_id": UC, "priority": "HIGH", "status": status}]}]})

    def ia(self):
        doc("planning/information-architecture/APP-001.md", "APP-001", "information-architecture",
            heads("information-architecture"), body="```mermaid\nflowchart TD\n  A-->B\n```\n")
        sync.stamp_doc(Workspace(), Workspace().docs["planning/information-architecture/APP-001.md"])

    def upstream(self):
        self.elicitation()
        self.overview()
        self.baseline()
        self.plan()
        self.ia()

    def repos_ready(self):
        (REPOS / "room-api").mkdir(exist_ok=True)
        ids.catalog_update("REPO-001", {"status": "ACTIVE"})

    def spec_docs(self):
        for st in schema.engine_steps():
            if st["phase"] == "SPECIFICATION":
                doc(Workspace().doc_rel(st["artifact_type"], UC), UC, st["artifact_type"], [], relations={})
        write(f"ui/prototypes/{UC}/index.html", "<html></html>")

    def delivery_doc(self, atype, **fm):
        doc(Workspace().doc_rel(atype, UC), UC, atype, [], relations={}, **fm)

    # ------------------------------------------------------------ run-level steps

    def test_fresh_template_waits_for_raw_material(self):
        _, d = derive()
        self.assertEqual(d["phase"], "ELICITATION")
        self.assertEqual(d["status"], "NOT_STARTED")
        self.assertIn("requirements/raw/", d["blocked_reason"])

    def test_elicitation_generate_then_stakeholder_wait_then_consolidate(self):
        write("requirements/raw/brief.md", "Stakeholder brief\n")
        _, d = derive()
        self.assertEqual(d["run_action"]["action"], "GENERATE")
        self.assertEqual(d["run_action"]["agent"], "elicitation-agent")

        self.elicitation()
        q = add("open-questions", question="Which rooms are bookable?", reason="Scope", impact_if_unanswered="Scope unknown",
                target_stakeholder="BUSINESS", priority="HIGH", status="OPEN", blocking=True)
        _, d = derive()
        self.assertEqual(d["status"], "WAITING_FOR_HUMAN")
        self.assertEqual(d["run_action"]["action"], "WAIT_FOR_STAKEHOLDERS")
        self.assertEqual([x["id"] for x in d["run_action"]["questions"]], [q])

        write("requirements/meetings/2026-10-02-workshop.md", "Answer: all rooms on floor 3.\n")
        _, d = derive()
        self.assertEqual(d["run_action"]["action"], "REGENERATE")      # step 2.6 consolidate the notes
        self.assertIn("requirements/meetings/", d["run_action"]["reason"])

        sync.stamp_doc(Workspace(), Workspace().docs["requirements/elicitation/elicitation-summary.md"])
        ids.catalog_update(q, {"status": "ANSWERED", "answer": "Floor 3"})
        _, d = derive()
        self.assertEqual(d["phase"], "OVERVIEW")
        self.assertEqual(d["run_action"]["agent"], "overview-analysis-agent")

    def test_overview_pre_review_then_gate_02_and_revise_goes_to_overview_agent(self):
        self.elicitation()
        self.overview()
        (paths.BA / "overview/integrations.yaml").unlink()
        _, d = derive()                          # GATE-02 reviews integrations.yaml: the step must create it
        self.assertEqual((d["run_action"]["action"], d["run_action"]["step"]), ("FIX", "OVERVIEW"))
        self.assertIn("catalog init", d["run_action"]["reason"])
        ids.catalog_init("integrations")
        _, d = derive()
        self.assertEqual((d["run_action"]["action"], d["run_action"]["agent"], d["run_action"]["round"]),
                         ("PRE_REVIEW", "review-agent", 1))
        passed("GATE-02", "RUN-001")
        _, d = derive()
        self.assertEqual(d["run_action"], {"action": "REQUEST_GATE", "gate": "GATE-02", "subject": "RUN-001",
                                           "reason": "NOT_REQUESTED"})
        _, d = derive(Gates().set("GATE-02@RUN-001", "CHANGES_REQUESTED", "add a cancellation rule"))
        self.assertEqual(d["run_action"]["action"], "REVISE")
        self.assertEqual((d["run_action"]["agent"], d["run_action"]["step"]), ("overview-analysis-agent", "OVERVIEW"))

    def test_pre_review_findings_route_to_owner_then_resolve_or_round_limit(self):
        self.elicitation()
        self.overview()
        prereview.record("GATE-02", "RUN-001", "FINDINGS", [
            {"artifact": "ba-ai/overview/use-cases.yaml", "severity": "MAJOR", "issue": "UC-001 lacks a requirement"}])
        _, d = derive()
        ra = d["run_action"]
        self.assertEqual((ra["action"], ra["agent"], ra["pre_review"]), ("REVISE", "overview-analysis-agent", True))
        self.assertIn("lacks a requirement", ra["comments"])

        prereview.resolve("GATE-02", "RUN-001", "REQ-001 covers it; the link is implicit")
        _, d = derive()
        self.assertEqual(d["run_action"]["action"], "REQUEST_GATE")
        self.assertIn("lacks a requirement", d["run_action"]["pre_review_findings"])

        # A changed artifact needs a fresh review, until the round limit (2) is reached.
        ids.catalog_update("UC-001", {"requirements": ["REQ-001"]}, force_gated=True)
        _, d = derive()
        self.assertEqual((d["run_action"]["action"], d["run_action"]["round"]), ("PRE_REVIEW", 2))
        prereview.record("GATE-02", "RUN-001", "FINDINGS", [
            {"artifact": "overview/use-cases.yaml", "severity": "MINOR", "issue": "wording"}])
        _, d = derive()
        self.assertEqual(d["run_action"]["action"], "REQUEST_GATE")       # 2 rounds done: the human decides

        with self.assertRaises(store.BAError):
            prereview.record("GATE-02", "RUN-001", "FINDINGS", [{"artifact": "ui/x.md", "issue": "not a gate artifact"}])

    def test_baseline_planning_and_ia_lead_into_the_spec_engine(self):
        self.elicitation()
        self.overview()
        g = Gates(GATE_02="APPROVED")
        _, d = derive(g)
        self.assertEqual((d["phase"], d["run_action"]["agent"]), ("TECH_BASELINE", "technical-baseline-agent"))
        self.baseline()
        _, d = derive(g)
        self.assertEqual((d["run_action"]["action"], d["run_action"]["gate"]), ("PRE_REVIEW", "GATE-09"))
        g.set("GATE-09", "APPROVED")
        _, d = derive(g)
        self.assertEqual((d["phase"], d["run_action"]["action"]), ("PLANNING", "GENERATE"))
        self.plan()
        _, d = derive(g)
        self.assertEqual((d["phase"], d["run_action"]["agent"]), ("INFORMATION_ARCHITECTURE", "planning-agent"))
        self.ia()
        ws, d = derive(g)
        self.assertEqual(d["phase"], "SPECIFICATION")
        r = d["use_cases"][UC]
        self.assertEqual((r["action"], r["step"], r["agent"]), ("GENERATE", "5.2", "ui-agent"))

    def test_new_use_case_after_planning_reopens_planning(self):
        self.upstream()
        add("use-cases", name="Cancel booking", business_process="BP-001", actor="ACT-001", application="APP-001",
            description="Cancel.", complexity="LOW", risk_level="LOW")
        _, d = derive(Gates(GATE_02="APPROVED", GATE_09="APPROVED"))
        self.assertEqual((d["phase"], d["run_action"]["action"]), ("PLANNING", "REGENERATE"))
        self.assertIn("UC-002", d["run_action"]["reason"])

    def test_approved_gate_freezes_upstream_steps(self):
        """Hand-written overviews (milestone 1 projects) are not regenerated once GATE-02 is approved."""
        self.elicitation()
        self.overview()
        (paths.BA / "requirements/elicitation/elicitation-summary.md").unlink()
        _, d = derive(Gates(GATE_02="APPROVED"))
        self.assertEqual(d["phase"], "TECH_BASELINE")

    # ------------------------------------------------------------ planning

    def test_plan_rejects_duplicates_cycles_and_keeps_progress(self):
        self.elicitation()
        self.overview()
        add("use-cases", name="Cancel", business_process="BP-001", actor="ACT-001", application="APP-001",
            description="Cancel.", complexity="LOW", risk_level="LOW")
        with self.assertRaises(store.BAError) as e:
            planning.apply_plan({"epics": [{"name": "A", "priority": "HIGH", "use_cases": [
                {"use_case_id": "UC-001", "priority": "HIGH", "dependencies": ["UC-002"]},
                {"use_case_id": "UC-002", "priority": "HIGH", "dependencies": ["UC-001"]}]}]})
        self.assertIn("cycle", str(e.exception))
        with self.assertRaises(store.BAError):
            planning.apply_plan({"epics": [
                {"name": "A", "priority": "HIGH", "use_cases": [{"use_case_id": "UC-001", "priority": "HIGH"}]},
                {"name": "B", "priority": "LOW", "use_cases": [{"use_case_id": "UC-001", "priority": "LOW"}]}]})
        res = self.plan()
        self.assertEqual(res["epics"], ["EPIC-001"])
        bl = store.load_yaml(paths.BACKLOG)
        bl["epics"][0]["use_cases"][0]["status"] = "IN_PROGRESS"
        bl["epics"][0]["use_cases"][0]["ui_status"] = "WAITING_FOR_REVIEW"
        store.save_yaml(paths.BACKLOG, bl)
        planning.apply_plan({"epics": [{"epic_id": "EPIC-001", "name": "Booking", "priority": "LOW", "use_cases": [
            {"use_case_id": UC, "priority": "LOW", "status": "BACKLOG"},
            {"use_case_id": "UC-002", "priority": "LOW", "status": "READY"}]}]})
        item = store.load_yaml(paths.BACKLOG)["epics"][0]["use_cases"][0]
        self.assertEqual((item["status"], item["ui_status"], item["priority"]), ("IN_PROGRESS", "WAITING_FOR_REVIEW", "LOW"))

    # ------------------------------------------------------------ delivery per use case

    def approved_spec(self, **more):
        g = Gates(GATE_02="APPROVED", GATE_09="APPROVED", GATE_03="APPROVED", GATE_04="APPROVED",
                  GATE_05="APPROVED")
        for k, v in more.items():
            g.set(k, v)
        return g

    def uc(self, g):
        _, d = derive(g, validate_docs=False)
        return d["use_cases"][UC], d

    def test_delivery_order_tests_first_qa_before_code_review(self):
        """D-37/D-38: GATE-06 → acceptance tests → code → QA → GATE-10 → user guide → GATE-08."""
        self.upstream()
        self.spec_docs()
        g = self.approved_spec()
        r, d = self.uc(g)
        self.assertEqual((r["action"], r["gate"], d["phase"]), ("PRE_REVIEW", "GATE-06", "TECHNICAL_REVIEW"))
        passed("GATE-06")
        r, _ = self.uc(g)
        self.assertEqual((r["action"], r["gate"]), ("REQUEST_GATE", "GATE-06"))

        g.set("GATE-06", "CHANGES_REQUESTED", "use PATCH")
        r, _ = self.uc(g)
        self.assertEqual((r["action"], r["agent"], r["steps"]), ("REVISE", "technical-analysis-agent", ["5.4", "5.5"]))

        g.set("GATE-06", "APPROVED")
        r, _ = self.uc(g)                        # the repository doesn't exist yet (D-39)
        self.assertEqual((r["action"], r["agent"], r["shared"]), ("SETUP_REPOSITORIES", "coding-agent", True))
        self.repos_ready()
        r, d = self.uc(g)
        self.assertEqual((r["action"], r["step"], r["agent"], d["phase"]), ("GENERATE", "8.1", "qa-agent", "TEST_DESIGN"))
        self.assertEqual(r["pre_command"], f"tools/ba coding authorize {UC}")

        self.delivery_doc("test-cases")
        r, _ = self.uc(g)
        self.assertEqual((r["action"], r["step"], r["agent"]), ("GENERATE", "7", "coding-agent"))
        self.delivery_doc("implementation", repositories=["REPO-001"], branch="ba/UC-001-book",
                          code_refs=["CODE:room-api/src/booking.py"])
        r, _ = self.uc(g)
        self.assertEqual((r["action"], r["step"], r["agent"]), ("GENERATE", "8.2", "qa-agent"))

        self.delivery_doc("test-results", outcome="PASSED", executed_at="2026-10-02T10:00:00Z")
        r, _ = self.uc(g)                        # QA passed → code review of the final code
        self.assertEqual((r["action"], r["gate"]), ("PRE_REVIEW", "GATE-10"))
        passed("GATE-10")
        r, _ = self.uc(g)
        self.assertEqual((r["action"], r["gate"]), ("REQUEST_GATE", "GATE-10"))
        g.set("GATE-10", "CHANGES_REQUESTED", "extract the overlap check")
        r, _ = self.uc(g)
        self.assertEqual((r["action"], r["agent"], r["steps"]), ("REVISE", "coding-agent", ["7"]))

        g.set("GATE-10", "APPROVED")
        r, _ = self.uc(g)                        # LOW risk: GATE-07 is skipped (D-23)
        self.assertEqual((r["action"], r["step"], r["agent"]), ("GENERATE", "9", "documentation-agent"))
        ws = Workspace()
        self.assertEqual(sync.stage_status(ws, g, UC, schema.engine()["stages"]["testing_status"], r), "DONE")
        self.assertEqual(sync.stage_status(ws, g, UC, schema.engine()["stages"]["coding_status"], r), "DONE")

        self.delivery_doc("user-guide")
        passed("GATE-08")
        r, _ = self.uc(g)
        self.assertEqual((r["action"], r["gate"]), ("REQUEST_GATE", "GATE-08"))
        g.set("GATE-08", "APPROVED")
        r, d = self.uc(g)
        self.assertEqual(r["state"], "DONE")
        self.assertEqual(d["status"], "COMPLETED")

    def test_high_risk_use_case_needs_critical_flow_test_after_code_review(self):
        self.upstream()
        ids.catalog_update(UC, {"risk_level": "HIGH", "risk_flags": ["FINANCIAL"]}, force_gated=True)
        _, d = derive(Gates(GATE_02="APPROVED", GATE_09="APPROVED"))
        self.assertEqual((d["phase"], d["run_action"]["action"]), ("INFORMATION_ARCHITECTURE", "REGENERATE"))
        self.ia()
        self.spec_docs()
        self.repos_ready()
        g = self.approved_spec(GATE_06="APPROVED", GATE_10="APPROVED")
        for t in ("test-cases", "implementation"):
            self.delivery_doc(t)
        self.delivery_doc("test-results", outcome="PASSED", executed_at="x")
        r, _ = self.uc(g)                        # GATE-07 has no AI pre-review: it is a human test
        self.assertEqual((r["action"], r["gate"]), ("REQUEST_GATE", "GATE-07"))
        ws = Workspace()
        self.assertEqual(sync.stage_status(ws, g, UC, schema.engine()["stages"]["testing_status"], r), "IN_PROGRESS")
        g.set("GATE-07", "CHANGES_REQUESTED", "booking overlaps were accepted")
        r, _ = self.uc(g)
        self.assertEqual((r["action"], r["agent"]), ("REVISE", "qa-agent"))

    def qa_failure(self, cls, attempts=0, status="OPEN"):
        self.upstream()
        self.spec_docs()
        self.repos_ready()
        g = self.approved_spec(GATE_06="APPROVED")
        for t in ("test-cases", "implementation"):
            self.delivery_doc(t)
        self.delivery_doc("test-results", outcome="FAILED", executed_at="2026-10-02T10:00:00Z")
        self.delivery_doc("defects", defects=[{"id": "UC-001-DEF-01", "classification": cls, "status": status,
                                               "fix_attempts": attempts}])
        return g

    def test_code_defect_goes_to_the_fix_loop_before_any_human_review(self):
        g = self.qa_failure("CODE_DEFECT", attempts=1)
        r, _ = self.uc(g)
        self.assertEqual((r["action"], r["step"], r["agent"]), ("FIX_DEFECT", "8.4", "coding-agent"))
        self.assertIn("attempt 2 of 3", r["reason"])
        self.assertEqual(r["pre_command"], f"tools/ba coding authorize {UC}")

    def test_fix_loop_stops_after_three_attempts(self):
        g = self.qa_failure("CODE_DEFECT", attempts=3)
        r, d = self.uc(g)
        self.assertEqual(r["state"], "NEEDS_HUMAN")
        self.assertEqual(d["status"], "WAITING_FOR_HUMAN")
        ws = Workspace()
        self.assertEqual(sync.stage_status(ws, g, UC, schema.engine()["stages"]["testing_status"], r), "BLOCKED")

    def test_test_issue_and_spec_gap_routing(self):
        g = self.qa_failure("TEST_ISSUE")
        r, _ = self.uc(g)
        self.assertEqual((r["action"], r["agent"], r["steps"]), ("FIX_TESTS", "qa-agent", ["8.1"]))
        self.setUp()
        g = self.qa_failure("SPECIFICATION_GAP")
        r, _ = self.uc(g)
        self.assertEqual(r["state"], "NEEDS_HUMAN")
        self.assertIn("SPECIFICATION_GAP", r["reason"])

    def test_retest_request_reruns_tests(self):
        g = self.qa_failure("ENVIRONMENT_ISSUE")
        Workspace().docs[f"qa/test-results/{UC}.md"].write_fm({"retest_requested_at": "2026-10-03T00:00:00Z"})
        r, _ = self.uc(g)
        self.assertEqual((r["action"], r["step"]), ("REGENERATE", "8.2"))

    # ------------------------------------------------------------ coding authorization and worktrees

    def test_coding_authorization_governs_repositories_and_their_worktrees(self):
        self.upstream()
        ws = Workspace()
        self.assertTrue(coding.problems(ws, Gates(), UC))
        self.assertEqual(coding.problems(ws, self.approved_spec(GATE_06="APPROVED"), UC), [])
        repo = REPOS / "room-api"
        wt = coding.worktree_path(repo, UC)
        self.assertEqual(wt, REPOS / "room-api-worktrees" / UC)
        for target in (repo / "src" / "x.py", wt / "src" / "x.py"):
            ok, why = coding.write_allowed(target, ws)
            self.assertFalse(ok, target)
            self.assertIn("coding authorize", why)
        self.assertEqual(coding.write_allowed(FIXTURE / "ba-ai" / "x.md", ws), (True, None))
        self.assertEqual(coding.write_allowed(REPOS / "unrelated" / "x.txt", ws), (True, None))
        ws.state["coding_authorization"] = {"use_cases": [UC]}
        real = engine.GateCache
        engine.GateCache = lambda _ws: self.approved_spec(GATE_06="APPROVED")
        try:
            self.assertEqual(coding.write_allowed(wt / "src" / "x.py", ws), (True, None))
        finally:
            engine.GateCache = real
        self.assertEqual(coding.repositories_ready(ws)[0], False)
        self.repos_ready()
        self.assertEqual(coding.repositories_ready(Workspace()), (True, []))

    # ------------------------------------------------------------ compiled specification (D-43)

    def test_compile_assembles_generated_sections_and_guards_them(self):
        self.upstream()
        self.spec_docs()
        write(f"specifications/analysis/{UC}-activity.md", "---\n" + store.dump_yaml({
            "id": UC, "artifact_type": "activity-validation", "title": "A", "status": "DRAFT", "version": 1,
            "baseline": "TO_BE", "origin": "FIXTURE", "updated_at": "", "relations": {"business_rules": ["BR-001"]}})
            + f"---\n## Validation Rules\n\n### {UC}-VR-01 — No overlap\n- **Enforces:** BR-001\n\n"
              f"## Error Flows\n\n### {UC}-EF-01 — Room taken\n- **Trigger:** overlap\n")
        write(f"technical/sequence/{UC}.md", "---\n" + store.dump_yaml({
            "id": UC, "artifact_type": "sequence", "title": "S", "status": "DRAFT", "version": 1,
            "baseline": "TO_BE", "origin": "FIXTURE", "updated_at": "", "relations": {}})
            + "---\n## Main Flow\n```mermaid\nsequenceDiagram\n  U->>W: book\n```\n1. Book.\n")
        res = spec_compile.compile_spec(UC)
        self.assertEqual(len(res["narrative_todo"]), 7)
        ws = Workspace()
        spec = ws.docs[f"specifications/use-cases/{UC}.md"]
        self.assertIn(f"### {UC}-VR-01 — No overlap", spec.body)
        self.assertIn("sequenceDiagram", spec.body)
        self.assertIn("BR-001 — No overlap:** Bookings may not overlap.", spec.body)
        self.assertTrue(any("TODO placeholder" in m for m in spec_compile.check(ws, spec)))

        # The agent writes the narrative; a recompile keeps it.
        p = paths.BA / f"specifications/use-cases/{UC}.md"
        text = p.read_text().replace("<!-- TODO(spec-agent): the goal, in business terms (use case description, "
                                     "requirements) -->", "Employees book a free room.")
        p.write_text(text)
        spec_compile.compile_spec(UC)
        self.assertIn("Employees book a free room.", p.read_text())

        # A hand edit to a generated section is caught.
        p.write_text(p.read_text().replace("Bookings may not overlap.", "Bookings may overlap."))
        ws = Workspace()
        msgs = spec_compile.check(ws, ws.docs[f"specifications/use-cases/{UC}.md"])
        self.assertTrue(any("11. Business Rules differs from its source" in m for m in msgs), msgs)

    # ------------------------------------------------------------ validation

    def test_validation_of_test_cases_defects_and_lifecycle(self):
        self.upstream()
        write(f"specifications/analysis/{UC}-acceptance.md", "---\n" + store.dump_yaml({
            "id": UC, "artifact_type": "acceptance-criteria", "title": "AC", "status": "DRAFT", "version": 1,
            "baseline": "TO_BE", "origin": "FIXTURE", "updated_at": "", "relations": {},
            "built_from": [{"ref": UC, "hash": "x"}]}) + "---\n## Acceptance Criteria\n\n"
            f"### {UC}-AC-01 — Books\n- **Given** a room\n- **When** booked\n- **Then** saved\n\n"
            f"### {UC}-AC-02 — Rejects overlap\n- **Given** a booking\n- **When** overlapping\n- **Then** 409\n\n"
            "## Coverage\n")
        tc = ids.next_id("TC")
        write(f"qa/test-cases/{UC}.md", "---\n" + store.dump_yaml({
            "id": UC, "artifact_type": "test-cases", "title": "TC", "status": "DRAFT", "version": 1,
            "baseline": "TO_BE", "origin": "FIXTURE", "updated_at": "", "relations": {},
            "built_from": [{"ref": UC, "hash": "x"}]}) + "---\n## Test Cases\n\n"
            f"### {tc} — Book a free room\n- **Verifies:** {UC}-AC-01\n- **Category:** Functional\n"
            "- **Automation:** api\n- **Steps:** book\n- **Expected:** saved\n\n"
            "### TC-999 — Invented\n- **Verifies:** UC-001-AC-01\n\n## Coverage\n")
        write(f"qa/defects/{UC}.md", "---\n" + store.dump_yaml({
            "id": UC, "artifact_type": "defects", "title": "D", "status": "DRAFT", "version": 1,
            "baseline": "TO_BE", "origin": "FIXTURE", "updated_at": "", "relations": {},
            "built_from": [{"ref": UC, "hash": "x"}],
            "defects": [{"id": f"{UC}-DEF-01", "classification": "BUG", "status": "OPEN", "fix_attempts": 5}]})
            + "---\n## Defects\n\n### UC-001-DEF-02 — Undeclared\n")
        msgs = [str(i) for i in validate(Workspace()) if i.level == "ERROR"]
        text = "\n".join(msgs)
        self.assertIn(f"{UC}-AC-02 is not verified by any test case", text)
        self.assertIn("TC-999 was never allocated", text)
        self.assertIn("'test_files' must list the automated acceptance tests", text)
        self.assertIn("'tests_commit' must map", text)
        self.assertIn("classification must be one of", text)
        self.assertIn("fix_attempts must be 0–3", text)
        self.assertIn("UC-001-DEF-02 has a section but is missing", text)
        self.assertIn("UC-001-DEF-01 has no", text)

        with self.assertRaises(store.BAError) as e:
            add("entities", name="Room", description="A room", owner="x", attributes=[{"name": "id", "type": "id"}],
                lifecycle={"states": ["FREE"], "transitions": ["FREE -> BOOKED: booked"]})
        self.assertIn("'BOOKED', which is not in states", str(e.exception))

    def test_run_step_stamp_records_optional_empty_input(self):
        self.elicitation()
        fm = Workspace().docs["requirements/elicitation/elicitation-summary.md"].fm
        entries = {e["path"]: e for e in fm["built_from"]}
        self.assertTrue(entries["requirements/meetings/"]["optional"])
        self.assertIsNone(entries["requirements/meetings/"]["hash"])
        self.assertIsNotNone(entries["requirements/raw/"]["hash"])


if __name__ == "__main__":
    unittest.main()
