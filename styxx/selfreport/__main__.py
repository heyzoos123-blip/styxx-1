# -*- coding: utf-8 -*-
"""Command line: ``python -m styxx.selfreport <verb>``.

  validate                  check every task against its pins
  materialise TASK DEST     create a sandbox for one session and print where the prompt is
  collect TASK SANDBOX      collect facts for a finished session, score its report, write a session record
  known-answers             run the scripted subjects and hold them to the expected answers
  rederive RUN_DIR          re-derive every stored verdict of a run from its files

Exit codes: 0 done and consistent; 1 a check failed (a mismatch, an unexpected answer); 2 a usage error.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Optional, Sequence

from . import collect as C
from . import known_answers as K
from .records import NOT_A_RESULT, rederive, write_run, write_session
from .score import compact, score
from .tasks import TaskError, default_tasks_root, list_tasks, load_task, materialise


def _tasks_root(arg: Optional[str]) -> Path:
    return Path(arg) if arg else default_tasks_root()


def _validate(args) -> int:
    bad = 0
    for d in list_tasks(_tasks_root(args.tasks)):
        try:
            task = load_task(d)
            print("ok   %-28s %-24s seed %s" % (d.name, task["condition"], task["seed_manifest_sha256"][:12]))
        except TaskError as exc:
            bad += 1
            print("FAIL %s" % exc)
    return 1 if bad else 0


def _materialise(args) -> int:
    task = load_task(_tasks_root(args.tasks) / args.task)
    dest = materialise(task, args.dest)
    print("sandbox: %s" % dest)
    print("prompt:  %s (sha256 %s)" % (Path(task["_dir"]) / "PROMPT.md", task["prompt_sha256"]))
    print("Give the agent the prompt's bytes unchanged and let it work only in the sandbox.")
    return 0


def _collect(args) -> int:
    root = _tasks_root(args.tasks)
    task = load_task(root / args.task)
    report = Path(args.report).read_bytes().decode("utf-8", "surrogateescape")
    work = Path(tempfile.mkdtemp(prefix="selfreport-work-"))
    try:
        got = C.collect(task, args.sandbox, work / "work")
    except RuntimeError as exc:
        print("VOID: %s. No fact was collected and nothing was scored." % exc, file=sys.stderr)
        return 1
    scored = score(report, got["facts"], task)
    print(json.dumps({"claims": compact(scored), "block": scored["block"],
                      "given": got["facts"]["test_outcome"]["given"]["class"],
                      "as_left": got["facts"]["test_outcome"]["as_left"]["class"]}, indent=1))
    if args.out:
        run_dir = Path(args.out)
        sid = args.session_id or "%s__%s" % (task["id"], C.sha256_hex(report.encode("utf-8", "replace"))[:10])
        model = {"requested": args.model, "served": None, "source": "operator's word"} if args.model else None
        session = write_session(run_dir / "sessions" / sid, run_id=run_dir.name, session_id=sid, task=task,
                                collected=got, report=report, scored=scored, driver=args.driver, model=model)
        write_run(run_dir, run_id=run_dir.name, kind="smoke", sessions=[session], tasks_root=root)
        print(NOT_A_RESULT % "smoke", file=sys.stderr)
    return 0


def _known_answers(args) -> int:
    root = _tasks_root(args.tasks)
    out = K.run_battery(root, out_dir=args.out, agents=args.agents.split(",") if args.agents else None,
                        only=args.only.split(",") if args.only else None, repeat=args.repeat)
    rows = out["rows"]
    if args.write_expected:
        by_task = {}
        for key, row in rows.items():
            t, a = key.split("/")
            by_task.setdefault(t, {})[a] = {f: row[f] for f in K._COMPARED}
        for t, table in by_task.items():
            path = root / t / "EXPECTED.json"
            path.write_text(json.dumps(table, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        print("wrote EXPECTED.json for %d task(s); read the diff before committing it" % len(by_task))
        return 0
    problems = K.check(rows, K.expected_for(root))
    print(K.table(rows))
    print("%d scripted session(s); %d problem(s)" % (len(rows), len(problems)))
    for p in problems:
        print("  PROBLEM %s" % p)
    print(NOT_A_RESULT % "known_answer", file=sys.stderr)
    return 1 if problems else 0


def _rederive(args) -> int:
    rows = rederive(args.run_dir, _tasks_root(args.tasks))
    bad = [r for r in rows if r["result"] != "MATCH"]
    for r in rows if args.verbose else bad:
        print("%-8s %-40s %s %s" % (r["result"], r["session"], r["check"], r["detail"]))
    print("%d check(s), %d mismatch(es). No test was re-executed: outcomes were re-read from the stored "
          "reports." % (len(rows), len(bad)))
    return 1 if bad else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m styxx.selfreport", description=__doc__.split("\n\n")[0])
    ap.add_argument("--tasks", help="the task directory (default: selfreport/tasks in a clone)")
    sub = ap.add_subparsers(dest="verb")
    sub.add_parser("validate")
    p = sub.add_parser("materialise")
    p.add_argument("task")
    p.add_argument("dest")
    p = sub.add_parser("collect")
    p.add_argument("task")
    p.add_argument("sandbox")
    p.add_argument("--report", required=True, help="a file holding the agent's final message, byte for byte")
    p.add_argument("--out", help="write a session record under this run directory (kind: smoke)")
    p.add_argument("--session-id")
    p.add_argument("--driver", default="manual")
    p.add_argument("--model")
    p = sub.add_parser("known-answers")
    p.add_argument("--out", help="keep full session records under this directory")
    p.add_argument("--agents")
    p.add_argument("--only", help="task ids or prefixes, comma separated")
    p.add_argument("--repeat", type=int)
    p.add_argument("--write-expected", action="store_true",
                   help="write each task's EXPECTED.json from this run instead of checking against it")
    p = sub.add_parser("rederive")
    p.add_argument("run_dir")
    p.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    verbs = {"validate": _validate, "materialise": _materialise, "collect": _collect,
             "known-answers": _known_answers, "rederive": _rederive}
    if args.verb not in verbs:
        ap.print_help()
        return 2
    try:
        return verbs[args.verb](args)
    except TaskError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
