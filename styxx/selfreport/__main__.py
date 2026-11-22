# -*- coding: utf-8 -*-
"""Command line: ``python -m styxx.selfreport <verb>``.

  validate                  check every task against its pins, and run each untouched seed
  materialise TASK DEST     create a sandbox for one session and print where the prompt is
  collect TASK SANDBOX      collect facts for a finished session, score its report, write a session record
  pin TASK_DIR              recompute a task's digests after changing its seed or prompt
  known-answers             run the scripted subjects and hold them to the expected answers
  rederive RUN_DIR          re-derive every stored verdict of a run from its files

Exit codes: 0 done and consistent; 1 a check failed (a mismatch, an unexpected answer, a void session);
2 a usage error.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional, Sequence

from . import collect as C
from . import known_answers as K
from .records import NOT_A_RESULT, rederive, run_digest, write_run, write_session
from .score import compact, score
from .tasks import (TaskError, check_seed, default_tasks_root, list_tasks, load_task, materialise, pin,
                    read_materialised)


def _tasks_root(arg: Optional[str]) -> Path:
    return Path(arg) if arg else default_tasks_root()


def _validate(args) -> int:
    bad = 0
    for d in list_tasks(_tasks_root(args.tasks)):
        try:
            task = load_task(d)
        except TaskError as exc:
            bad += 1
            print("FAIL %s" % exc)
            continue
        problems = [] if args.no_run else check_seed(task)
        bad += bool(problems)
        print("%-4s %-28s %-24s seed %s" % ("FAIL" if problems else "ok", d.name, task["condition"],
                                            task["seed_manifest_sha256"][:12]))
        for p in problems:
            print("     %s" % p)
    return 1 if bad else 0


def _materialise(args) -> int:
    task = load_task(_tasks_root(args.tasks) / args.task)
    dest = materialise(task, args.dest)
    print("sandbox: %s" % dest)
    print("prompt:  %s (sha256 %s)" % (Path(task["_dir"]) / "PROMPT.md", task["prompt_sha256"]))
    print("Give the agent the prompt's bytes unchanged and let it work only in the sandbox.")
    return 0


def _pin(args) -> int:
    task = pin(args.task_dir)
    print("pinned %s: seed %s, prompt %s" % (task["id"], task["seed_manifest_sha256"][:12],
                                            task["prompt_sha256"][:12]))
    return 0


def _collect(args) -> int:
    root = _tasks_root(args.tasks)
    task = load_task(root / args.task)
    raw = Path(args.report).read_bytes()
    report = raw.decode("utf-8", "surrogateescape")
    run_dir = Path(args.out) if args.out else None
    try:
        tree = C.manifest_digest(C.manifest(args.sandbox))[:8]
    except (C.Void, OSError):
        tree = "unread"  # the tree cannot be read; collect() below says why and the session is void
    sid = args.session_id or "%s__%s_%s" % (task["id"], C.sha256_hex(raw)[:8], tree)
    if run_dir is not None and (run_dir / "sessions" / sid).exists():
        print("error: a session %s is already recorded in %s" % (sid, run_dir), file=sys.stderr)
        return 2
    work = Path(tempfile.mkdtemp(prefix="selfreport-work-"))
    try:
        try:
            got = C.collect(task, args.sandbox, work / "work", materialised=read_materialised(args.sandbox))
        except C.Void as exc:
            print("VOID: %s. No fact was collected and nothing was scored." % exc, file=sys.stderr)
            if run_dir is not None:
                write_run(run_dir, run_id=run_dir.name, kind="smoke", tasks_root=root,
                          void=[{"session_id": sid, "task": task["id"], "reason": str(exc),
                                 "report_sha256": C.sha256_hex(raw)}])
            return 1
        scored = score(report, got["facts"], task)
        print(json.dumps({"claims": compact(scored), "block": scored["block"],
                          "given": got["facts"]["test_outcome"]["given"]["class"],
                          "as_left": got["facts"]["test_outcome"]["as_left"]["class"],
                          "outside_allowed_paths": got["facts"]["compliance"]["outside"]}, indent=1))
        if run_dir is not None:
            model = {"requested": args.model, "served": None, "source": "operator's word"} if args.model else None
            write_session(run_dir / "sessions" / sid, run_id=run_dir.name, session_id=sid, task=task,
                          collected=got, report=report, scored=scored, driver=args.driver, model=model)
            write_run(run_dir, run_id=run_dir.name, kind="smoke", tasks_root=root)
            print(NOT_A_RESULT % "smoke", file=sys.stderr)
    finally:
        shutil.rmtree(str(work), ignore_errors=True)
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
            by_task.setdefault(t, {})[a] = {f: row[f] for f in K.COMPARED}
        for t, table in by_task.items():
            C.write_lf(root / t / "EXPECTED.json", json.dumps(table, indent=1, sort_keys=True) + "\n")
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
    bad = [r for r in rows if r["result"] == "MISMATCH"]
    notes = [r for r in rows if r["result"] == "NOTE"]
    for r in rows if args.verbose else bad + notes:
        print("%-8s %-40s %s %s" % (r["result"], r["session"], r["check"], r["detail"]))
    run = json.loads((Path(args.run_dir) / "run.json").read_text(encoding="utf-8"))
    print("%d check(s), %d mismatch(es). No test was re-executed: outcomes were re-read from the stored "
          "reports." % (len(rows), len(bad)))
    print("run kind: %s. sha256(run.json): %s" % (run.get("kind"), run_digest(args.run_dir)))
    if run.get("statement"):
        print(run["statement"])
    return 1 if bad else 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m styxx.selfreport", description=__doc__.split("\n\n")[0])
    ap.add_argument("--tasks", help="the task directory (default: selfreport/tasks in a clone)")
    sub = ap.add_subparsers(dest="verb")
    p = sub.add_parser("validate")
    p.add_argument("--no-run", action="store_true", help="check the pins only; do not run the seeds")
    p = sub.add_parser("materialise")
    p.add_argument("task")
    p.add_argument("dest")
    p = sub.add_parser("pin")
    p.add_argument("task_dir")
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
    verbs = {"validate": _validate, "materialise": _materialise, "pin": _pin, "collect": _collect,
             "known-answers": _known_answers, "rederive": _rederive}
    if args.verb not in verbs:
        ap.print_help()
        return 2
    try:
        return verbs[args.verb](args)
    except (TaskError, C.Void) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
