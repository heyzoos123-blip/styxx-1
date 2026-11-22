# -*- coding: utf-8 -*-
"""Shared helpers for tests/test_selfreport_*.py (not a test module)."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

from styxx.selfreport import collect as C
from styxx.selfreport import tasks as T

ROOT = T.default_tasks_root()


def _why_not():
    if sys.platform == "win32":
        return "the collector has been run on Linux only; it starts git and pytest in subprocesses"
    if shutil.which("git") is None:
        return "needs git"
    inside = C.inside_repository(Path(tempfile.gettempdir()).resolve())
    if inside is not None:
        return "the temporary directory is inside a repository (%s); sandboxes must sit outside one" % inside
    return None


#: Marks tests that build sandboxes and start subprocesses. Skipped, with the reason, where that cannot work.
needs_sandbox = pytest.mark.skipif(_why_not() is not None, reason=_why_not() or "")


def write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    C.write_lf(path, text)


def copy_set(tmp_path):
    """A private copy of the task set (tasks and contract) that a test may damage."""
    dest = Path(tmp_path) / "selfreport"
    shutil.copytree(str(ROOT.parent), str(dest))
    return dest / "tasks"


def make_task(tmp_path, base, new_id, files, **updates):
    """A new task in a private copy of the set: ``base``'s directory copied, seed files replaced or added
    from ``files`` (``None`` deletes), ``task.json`` fields updated, pins recomputed. Returns the loaded task."""
    root = copy_set(tmp_path)
    d = root / new_id
    shutil.copytree(str(root / base), str(d))
    for rel, body in files.items():
        if body is None:
            (d / "seed" / rel).unlink()
        else:
            write(d / "seed" / rel, body)
    tj = json.loads((d / "task.json").read_text(encoding="utf-8"))
    tj["id"] = new_id
    tj.update(updates)
    write(d / "task.json", json.dumps(tj, indent=1) + "\n")
    if (d / "EXPECTED.json").exists():
        (d / "EXPECTED.json").unlink()
    T.pin(d)
    return T.load_task(d)


def session(tmp_path, task, act=None, repeat=1, name="s"):
    """Materialise ``task`` under ``tmp_path``, let ``act(sandbox)`` change it, collect. Returns
    ``(sandbox, collected)``."""
    home = Path(tmp_path) / name
    sandbox = T.materialise(task, home / "sandbox", environment=C.environment_fingerprint())
    if act is not None:
        act(sandbox)
    got = C.collect(task, sandbox, home / "work", repeat=repeat, materialised=T.read_materialised(sandbox))
    return sandbox, got


def outcome(got, mode="given"):
    return got["facts"]["test_outcome"][mode]["class"]


def block(**kv):
    return "Some prose.\n\n```styxx\n" + "\n".join("%s: %s" % (k, v) for k, v in kv.items()) + "\n```\n"
