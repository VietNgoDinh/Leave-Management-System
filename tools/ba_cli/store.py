"""File I/O, frontmatter, content hashing and locking shared by all ba commands."""
from __future__ import annotations

import contextlib
import datetime
import fcntl
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Optional, Tuple

import yaml

from . import paths


class BAError(Exception):
    """An expected, user-facing error. Printed without a traceback."""


def now() -> str:
    return (datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
            .isoformat().replace("+00:00", "Z"))


# ------------------------------------------------------------------ YAML / JSON

class _Dumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def _represent_str(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_Dumper.add_representer(str, _represent_str)


def dump_yaml(data: Any) -> str:
    return yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True,
                     default_flow_style=False, width=100)


def load_yaml(p: Path) -> Any:
    try:
        with open(p, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise BAError(f"{paths.rel(p)}: invalid YAML: {e}")


def write_atomic(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".tmp-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, p)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def save_yaml(p: Path, data: Any) -> None:
    write_atomic(p, dump_yaml(data))


def load_json(p: Path, default: Any = None) -> Any:
    if not p.exists():
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_json(p: Path, data: Any) -> None:
    write_atomic(p, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


# ------------------------------------------------------------------ locking

_lock_depth = 0
_lock_file = None


@contextlib.contextmanager
def locked():
    """Exclusive workspace lock for any write to shared files. Re-entrant per process."""
    global _lock_depth, _lock_file
    if _lock_depth == 0:
        paths.LOCK.parent.mkdir(parents=True, exist_ok=True)
        _lock_file = open(paths.LOCK, "a+")
        fcntl.flock(_lock_file, fcntl.LOCK_EX)
    _lock_depth += 1
    try:
        yield
    finally:
        _lock_depth -= 1
        if _lock_depth == 0:
            fcntl.flock(_lock_file, fcntl.LOCK_UN)
            _lock_file.close()
            _lock_file = None


# ------------------------------------------------------------------ frontmatter

_FM = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.S)


def split_frontmatter(text: str) -> Tuple[Optional[dict], str]:
    m = _FM.match(text)
    if not m:
        return None, text
    fm = yaml.safe_load(m.group(1)) or {}
    if not isinstance(fm, dict):
        raise BAError("frontmatter is not a mapping")
    return fm, text[m.end():]


def write_frontmatter(p: Path, fm: dict, body: str) -> None:
    write_atomic(p, "---\n" + dump_yaml(fm) + "---\n" + body)


# ------------------------------------------------------------------ hashing (D-09, D-11)

# Frontmatter keys that describe an artifact rather than being its content.
# Changing them never changes the content hash, so status updates keep approvals valid.
VOLATILE = ("status", "review", "updated_at", "version", "built_from")


def short_hash(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()[:16]


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str,
                      separators=(",", ":")).encode("utf-8")


def hash_markdown_text(text: str) -> str:
    fm, body = split_frontmatter(text)
    fm = {k: v for k, v in (fm or {}).items() if k not in VOLATILE}
    body = body.replace("\r\n", "\n").strip()
    return short_hash(canonical(fm) + b"\n---\n" + body.encode("utf-8"))


def hash_yaml_data(data: Any) -> str:
    if isinstance(data, dict) and isinstance(data.get("meta"), dict):
        data = dict(data)
        data["meta"] = {k: v for k, v in data["meta"].items() if k not in VOLATILE}
    return short_hash(canonical(data))


def hash_file(p: Path) -> str:
    if p.suffix == ".md":
        return hash_markdown_text(p.read_text(encoding="utf-8"))
    if p.suffix in (".yaml", ".yml"):
        return hash_yaml_data(load_yaml(p))
    return short_hash(p.read_bytes())


def hash_path(p: Path) -> Optional[str]:
    """Content hash of a file or directory; None if it does not exist."""
    if p.is_dir():
        files = sorted(
            f for f in p.rglob("*")
            if f.is_file() and not any(part.startswith(".") for part in f.relative_to(p).parts)
        )
        if not files:
            return None
        lines = "\n".join(f"{f.relative_to(p).as_posix()}:{hash_file(f)}" for f in files)
        return short_hash(lines.encode("utf-8"))
    if p.is_file():
        return hash_file(p)
    return None


def hash_item(item: Any) -> str:
    return short_hash(canonical(item))


def resolve_user_path(arg: str) -> Path:
    """Accept paths relative to cwd, to the workspace root, or to ba-ai/."""
    p = Path(arg)
    if p.is_absolute():
        return p
    for base in (Path.cwd(), paths.ROOT, paths.BA):
        q = base / arg
        if q.exists():
            return q.resolve()
    return (paths.BA / arg).resolve()
