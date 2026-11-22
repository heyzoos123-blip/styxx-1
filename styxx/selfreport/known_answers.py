# -*- coding: utf-8 -*-
"""Run the scripted subjects through the collector and the scorer, and hold the outcome to what was written
down in advance (each task's ``EXPECTED.json``).

Three things must hold before any model is run with this code, and this module checks all three:

1. Every scripted session receives exactly the expected verdicts and test outcomes.
2. The three history subjects receive identical facts on every task.
3. Wherever ``styxx.diffgate`` also gives a verdict on a declared claim, it never contradicts the
   comparison here (TRUE against CONTRADICTED, or FALSE against VERIFIED).
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from . import collect as C
from .records import write_run, write_session
from .score import compact, score
from .scripted import AGENTS, HISTORY_TRIO
from .tasks import list_tasks, load_task, materialise

#: diffgate's claim kinds, by the declaration key that produces them.
_GATE_KIND = {"files_changed": "files_changed_count", "tests_added": "tests_added",
              "only_touches": "only_touches", "tests_pass": "tests_pass"}


def _gate(report: str, diff_text: str):
    from styxx.diffgate import gate_diff_text

    return gate_diff_text(report, diff_text)


def _conflicts(scored: dict, gate) -> List[str]:
    out = []
    by_kind = {c.kind: c.verdict for c in gate.claims if c.detail.get("declared")}
    for key, claim in scored["claims"].items():
        g = by_kind.get(_GATE_KIND.get(key, key))
        v = claim["verdict"]
        if (v == "TRUE" and g == "CONTRADICTED") or (v == "FALSE" and g == "VERIFIED"):
            out.append("%s: comparison says %s, diffgate says %s" % (key, v, g))
    return out


def run_battery(tasks_root=None, out_dir=None, agents: Optional[Sequence[str]] = None,
                only: Optional[Sequence[str]] = None, repeat: Optional[int] = None,
                python: str = sys.executable, with_gate: bool = True, run_id: str = "known-answers") -> dict:
    """Run scripted subjects on tasks. Returns ``{"rows": {"task/agent": row}, "run_dir": path or None}``.

    With ``out_dir`` every session is written as a full record (kind ``known_answer``) that ``rederive``
    can check; without it nothing is kept.
    """
    names = list(agents) if agents else list(AGENTS)
    rows: Dict[str, dict] = {}
    sessions = []
    run_dir = Path(out_dir) if out_dir is not None else None
    if run_dir is not None:
        (run_dir / "sessions").mkdir(parents=True, exist_ok=True)
    task_dirs = [p for p in list_tasks(tasks_root) if not only or p.name in only
                 or any(p.name.startswith(o) for o in only)]
    for task_dir in task_dirs:
        task = load_task(task_dir)
        for name in names:
            td = Path(tempfile.mkdtemp(prefix="selfreport-"))
            try:
                sandbox = materialise(task, td / "sandbox")
                report = AGENTS[name](sandbox, task["id"])
                got = C.collect(task, sandbox, td / "work", python=python, repeat=repeat)
                scored = score(report, got["facts"], task)
                gate = _gate(report, got["diff_text"]) if with_gate else None
                f = got["facts"]
                row = {"claims": compact(scored), "block": scored["block"],
                       "given": f["test_outcome"]["given"]["class"],
                       "as_left": f["test_outcome"]["as_left"]["class"],
                       "changed": f["changed"]["count"], "tests_added_ast": len(f["tests_added"]["ast"]),
                       "facts_digest": C.facts_digest(f),
                       "conflicts": _conflicts(scored, gate) if gate is not None else []}
                rows["%s/%s" % (task["id"], name)] = row
                if run_dir is not None:
                    sid = "%s__%s" % (task["id"], name)
                    sessions.append(write_session(run_dir / "sessions" / sid, run_id=run_id, session_id=sid,
                                                  task=task, collected=got, report=report, scored=scored,
                                                  driver="scripted:%s" % name, gate=gate))
            finally:
                shutil.rmtree(str(td), ignore_errors=True)
    if run_dir is not None:
        write_run(run_dir, run_id=run_id, kind="known_answer", sessions=sessions,
                  tasks_root=task_dirs[0].parent if task_dirs else tasks_root, python=python)
    return {"rows": rows, "run_dir": str(run_dir) if run_dir is not None else None}


def expected_for(tasks_root=None) -> Dict[str, dict]:
    """Every task's EXPECTED.json, flattened to ``{"task/agent": {...}}``."""
    out: Dict[str, dict] = {}
    for task_dir in list_tasks(tasks_root):
        path = task_dir / "EXPECTED.json"
        if path.is_file():
            for agent, want in json.loads(path.read_text(encoding="utf-8")).items():
                out["%s/%s" % (task_dir.name, agent)] = want
    return out


_COMPARED = ("claims", "block", "given", "as_left", "changed", "tests_added_ast")


def check(rows: Dict[str, dict], expected: Dict[str, dict]) -> List[str]:
    """Every way ``rows`` falls short of the three requirements. An empty list is a pass."""
    problems: List[str] = []
    for key in sorted(rows):
        row = rows[key]
        want = expected.get(key)
        if want is None:
            problems.append("%s: no expected answer is written down" % key)
        else:
            for f in _COMPARED:
                if row[f] != want[f]:
                    problems.append("%s: %s is %r, expected %r" % (key, f, row[f], want[f]))
        for c in row["conflicts"]:
            problems.append("%s: conflict with diffgate: %s" % (key, c))
    tasks = sorted({k.split("/")[0] for k in rows})
    for t in tasks:
        digests = {rows["%s/%s" % (t, a)]["facts_digest"] for a in HISTORY_TRIO if "%s/%s" % (t, a) in rows}
        if len(digests) > 1:
            problems.append("%s: the history subjects received different facts" % t)
    return problems


def table(rows: Dict[str, dict]) -> str:
    """Per key, how many sessions received each verdict. No pooled rate over keys is ever printed: a subject
    that pads its block with easy true claims would dilute it."""
    counts: Dict[str, Dict[str, int]] = {}
    for row in rows.values():
        for key, verdict in row["claims"].items():
            counts.setdefault(key, {})
            counts[key][verdict] = counts[key].get(verdict, 0) + 1
    lines = []
    for key in sorted(counts):
        cells = ", ".join("%s %d" % (v, n) for v, n in sorted(counts[key].items()))
        lines.append("%-14s %s" % (key, cells))
    return "\n".join(lines)
