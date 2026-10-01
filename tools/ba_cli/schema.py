"""Access to tools/schemas/*.yaml and ba-ai/workflow/workflow.yaml."""
from __future__ import annotations

from functools import lru_cache
from typing import List, Optional

from . import paths, store


@lru_cache(None)
def catalogs() -> dict:
    return store.load_yaml(paths.SCHEMAS / "catalogs.yaml")["catalogs"]


@lru_cache(None)
def artifacts() -> dict:
    return store.load_yaml(paths.SCHEMAS / "artifacts.yaml")


def artifact_type(name: str) -> Optional[dict]:
    return artifacts()["artifact_types"].get(name)


def enum(name: str) -> List[str]:
    return artifacts()["enums"][name]


def relation_edges() -> dict:
    return artifacts()["relation_edges"]


@lru_cache(None)
def workflow() -> dict:
    return store.load_yaml(paths.WORKFLOW_YAML)


def gate(gate_id: str) -> Optional[dict]:
    return workflow()["gates"].get(gate_id)


def engine() -> dict:
    return workflow()["use_case_engine"]


def engine_steps() -> List[dict]:
    """Per-use-case steps that produce an artifact (5.2–5.8, 7, 8.1, 8.2, 9)."""
    return [s for s in engine()["steps"] if s.get("artifact_type")]


def uc_steps() -> List[dict]:
    """Per-use-case steps the engine walks: those with an artifact or a gate (5.1 is the orchestrator's)."""
    return [s for s in engine()["steps"] if s.get("artifact_type") or s.get("gate")]


def step_for_type(artifact_type_name: str) -> Optional[dict]:
    for s in engine_steps():
        if s["artifact_type"] == artifact_type_name:
            return s
    return None


def run_steps() -> dict:
    return workflow().get("run_steps") or {}


def run_step(step_id: str) -> Optional[dict]:
    return run_steps().get(step_id)


def optional_input(entry: str):
    """'requirements/meetings/?' → ('requirements/meetings/', True)."""
    return (entry[:-1], True) if entry.endswith("?") else (entry, False)


def run_output_for(rel: str) -> Optional[dict]:
    """The run-step output definition (path + built_from) that produces document `rel`."""
    import re
    for sid, sdef in run_steps().items():
        for out in sdef.get("outputs") or []:
            if out["path"] == rel:
                return {"step": sid, **out}
        pa = sdef.get("per_application")
        if pa:
            rx = "^" + re.escape(pa["path"]).replace(re.escape("{APP}"), r"(APP-\d{3,4})") + "$"
            m = re.match(rx, rel)
            if m:
                return {"step": sid, "path": rel, "app": m.group(1), "built_from": pa.get("built_from", [])}
    return None


def gate_required(gate_id: str, uc_item: Optional[dict]) -> bool:
    """D-23: GATE-07 applies only to risky use cases; every other gate always applies."""
    g = gate(gate_id) or {}
    if g.get("required_when") == "risk":
        item = uc_item or {}
        return item.get("risk_level") in ("HIGH", "CRITICAL") or bool(item.get("risk_flags"))
    return True


def catalog_for_path(rel: str) -> Optional[str]:
    for name, c in catalogs().items():
        if c["path"] == rel:
            return name
    return None
