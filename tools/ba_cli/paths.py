"""Workspace locations. Paths stored inside artifacts are relative to ba-ai/."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(os.environ.get("BA_ROOT") or Path(__file__).resolve().parents[2]).resolve()
BA = ROOT / "ba-ai"
SCHEMAS = ROOT / "tools" / "schemas"

WORKFLOW_YAML = BA / "workflow" / "workflow.yaml"
STATE = BA / "workflow" / "state.json"
CONTEXT_DIR = BA / "workflow" / "context"
BACKLOG = BA / "planning" / "backlog.yaml"
REGISTRY = BA / "knowledge" / "id-registry.json"
GRAPH = BA / "knowledge" / "ba-graph.json"
REQUESTS = BA / "reviews" / "requests"
DECISIONS = BA / "reviews" / "decisions"
LOCK = BA / ".ba.lock"


def rel(p: Path) -> str:
    """Posix path relative to ba-ai/ (or the absolute path if outside it)."""
    p = Path(p).resolve()
    try:
        return p.relative_to(BA).as_posix()
    except ValueError:
        return str(p)


def show(rel_path: str) -> str:
    """Path as the user sees it from the workspace root."""
    return "ba-ai/" + rel_path
