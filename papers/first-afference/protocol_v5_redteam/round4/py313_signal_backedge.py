"""Found by the third attack pass on the round-4 finding, re-checked here: on CPython 3.13, an ordinary
signal can hang v5e with no profile hook involved.

Two checks per interpreter, each in its own process:

1. THE INTERPRETER. Four loop shapes inside ``try/finally`` are each interrupted by a SIGALRM handler
   that raises KeyboardInterrupt: ``while cond``, a ``for`` loop whose body ends in an ``if``, a plain
   ``for``, and ``while True`` with ``if ...: break``. Does the ``finally`` run? The behaviour matches
   CPython issue #130279 (reported for a ``while`` condition on 3.13.1/3.13.2). The exception-table
   layout alone does not explain it: 3.12 leaves the same back-edge outside the table and still runs
   ``finally``. The difference is where 3.13 delivers a pending signal.
2. v5e. It builds a tracer with many openings, so that ``__exit__`` spends time in its ``with _LOCK:``
   loops. It arms SIGALRM (handler raises KeyboardInterrupt) to land during ``__exit__``, then asks
   whether another thread can still take ``_LOCK``. If the lock stays held, every later trace in the
   process hangs.

Writes py313_signal_backedge.json next to this file.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FA = HERE.parents[1]
SP = "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt3"
PYS = [sys.executable] + [f"{SP}/venv3.{v}/bin/python" for v in (10, 12, 13)]


def child_interpreter() -> dict:
    import dis
    import signal
    fin = []

    def while_cond():
        try:
            i = 0
            while i < 10 ** 9:
                i += 1
        finally:
            fin.append(1)

    def for_if():
        try:
            n = 0
            for i in range(10 ** 9):
                if i < 0:
                    n += 1
        finally:
            fin.append(1)

    def for_plain():
        try:
            for i in range(10 ** 9):
                pass
        finally:
            fin.append(1)

    def while_true_break():
        try:
            i = 0
            while True:
                i += 1
                if i > 10 ** 9:
                    break
        finally:
            fin.append(1)
    probe = while_cond

    def h(s, fr):
        raise KeyboardInterrupt
    signal.signal(signal.SIGALRM, h)
    shapes = {}
    for fn in (while_cond, for_if, for_plain, while_true_break):
        ran = []
        for _ in range(5):
            fin.clear()
            signal.setitimer(signal.ITIMER_REAL, 0.02)
            try:
                fn()
            except KeyboardInterrupt:
                pass
            ran.append(bool(fin))
        shapes[fn.__name__] = ran.count(False)
    runs = [shapes["while_cond"] == 0]
    table = []
    try:
        bc = dis.Bytecode(probe)
        table = [f"{e.start}-{e.end}->{e.target}" for e in bc.exception_entries]
        back = [ins.offset for ins in bc if ins.opname.startswith("JUMP_BACKWARD")]
        uncovered = [o for o in back if not any(e.start <= o < e.end for e in bc.exception_entries)]
    except AttributeError:                      # 3.10 has no exception table
        back, uncovered = [], []
    return {"finally_skipped_of_5_by_shape": shapes, "n_finally_skipped": shapes["while_cond"],
            "n_shapes_skipping": sum(1 for v in shapes.values() if v), "exception_table": table,
            "jump_backward_offsets": back, "jump_backward_outside_table": uncovered}


def child_v5e(n: int) -> dict:
    import signal
    sys.argv = ["x"]
    sys.path.insert(0, str(FA))
    import fault_injection_v5 as F
    env = F.Env()

    def build():
        exp = env.exp(G={"exercises": [F.T("f")]})
        cov = F.coverage_trace(exp)
        cov.__enter__()
        for _ in range(n):
            cov.run("G", env.mod.f, 1)
        return cov
    cov = build()
    t0 = time.perf_counter()
    cov.__exit__(None, None, None)
    dt = time.perf_counter() - t0
    F.force_reset(env)

    def h(s, fr):
        raise KeyboardInterrupt
    signal.signal(signal.SIGALRM, h)
    trials = []
    for k in range(4):
        cov = build()
        signal.setitimer(signal.ITIMER_REAL, dt * (0.3 + 0.1 * k))
        try:
            cov.__exit__(None, None, None)
            signal.setitimer(signal.ITIMER_REAL, 0)
            trials.append({"interrupted": False})
        except KeyboardInterrupt as e:
            import threading
            import traceback
            tb = traceback.extract_tb(e.__traceback__)
            v5 = [fr for fr in tb if fr.filename == F.P.__file__]
            last = v5[-1] if v5 else tb[-1]
            same = F.P._LOCK.acquire(timeout=0.5)            # the interrupted thread itself (RLock)
            if same:
                F.P._LOCK.release()
            trials.append({"interrupted": True, "v5e_frame": f"{last.name}:{last.lineno}",
                           "lock_free_for_other_thread": F.lock_free(0.5),
                           "same_thread_can_retake": bool(same)})
        F.force_reset(env)
    return {"n_openings": n, "exit_seconds": round(dt, 4), "trials": trials,
            "n_interrupted": sum(t["interrupted"] for t in trials),
            "n_lock_left_held": sum(1 for t in trials if t.get("lock_free_for_other_thread") is False),
            "n_same_thread_can_retake": sum(1 for t in trials if t.get("same_thread_can_retake"))}


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        what = sys.argv[2]
        out = child_interpreter() if what == "interp" else child_v5e(int(sys.argv[3]))
        print(json.dumps(out))
        return 0
    per = {}
    for py in PYS:
        if not Path(py).exists():
            continue
        v = subprocess.run([py, "-c", "import sys;print(sys.version.split()[0])"],
                           capture_output=True, text=True).stdout.strip()
        row = {}
        for what, extra in (("interp", []), ("v5e", ["100000"])):
            p = subprocess.run([py, __file__, "--child", what, *extra], capture_output=True, text=True,
                               timeout=900, cwd=HERE)
            try:
                row[what] = json.loads(p.stdout.strip().splitlines()[-1])
            except Exception:                                    # noqa: BLE001
                row[what] = {"error": (p.stderr or p.stdout)[-400:]}
        per[v] = row
    res = {"what": "does a signal exception at a while-loop back-edge skip finally (CPython #130279), and does it "
                   "leave v5e's _LOCK held during tracer exit? one row per interpreter",
           "generator": "papers/first-afference/protocol_v5_redteam/round4/py313_signal_backedge.py",
           "generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           "upstream_issue": "https://github.com/python/cpython/issues/130279",
           "per_version": per,
           "versions_skipping_finally": sorted(v for v, r in per.items() if r["interp"].get("n_finally_skipped")),
           "versions_leaving_lock_held": sorted(v for v, r in per.items() if r["v5e"].get("n_lock_left_held"))}
    (HERE / "py313_signal_backedge.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for v, r in per.items():
        print(v, "finally skipped by shape", r["interp"].get("finally_skipped_of_5_by_shape"), "| while backedge outside table",
              r["interp"].get("jump_backward_outside_table"), "| v5e lock left held",
              r["v5e"].get("n_lock_left_held"), "/", r["v5e"].get("n_interrupted"), "interrupted; same thread retakes",
              r["v5e"].get("n_same_thread_can_retake"), "; frames", sorted({t.get("v5e_frame") for t in r["v5e"].get("trials", []) if t.get("interrupted")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
