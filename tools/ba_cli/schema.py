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
    """Spec-engine steps that produce an artifact (5.2–5.8)."""
    return [s for s in engine()["steps"] if s.get("artifact_type")]


def step_for_type(artifact_type_name: str) -> Optional[dict]:
    for s in engine_steps():
        if s["artifact_type"] == artifact_type_name:
            return s
    return None


def catalog_for_path(rel: str) -> Optional[str]:
    for name, c in catalogs().items():
        if c["path"] == rel:
            return name
    return None
