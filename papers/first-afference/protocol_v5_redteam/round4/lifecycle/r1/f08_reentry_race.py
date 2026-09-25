"""Lifecycle / REENTRY is racy: two threads entering the same tracer object both get in.

__enter__ checks `self._state != "new"` outside _LOCK and sets `self._state = "active"` only at the
end, after resolving every target (imports, resolution) and minting.  Two threads that enter one
tracer object at about the same time both pass the check, so neither gets REENTRY; the second
entry appends the tracer to m.tracers again, duplicates every declared name in _by_code (so every
hit is counted twice) and increments _ACTIVE a second time.  Only the first __exit__ does anything
(the second sees state 'exited' and returns), so _ACTIVE stays 1 for ever after both with-blocks
have exited, and the trace carries no REENTRY problem.

Harness shape (accidental): a module-level `COV = coverage_trace(exp)` used as `with COV:` by each
worker thread of a parallel runner.  The window is __enter__'s resolution: when the declared module
is not imported yet (the normal case for the first trace of a run), the import does file I/O and
releases the GIL, and the other thread passes the state check meanwhile.  Each attempt below drops
the declared module from sys.modules first, so the import really happens.

Spec: "__enter__ 1. If the state is not `new`, refuse REENTRY. This refusal is recorded if the
tracer was ever entered."  Reason codes: "REENTRY | __enter__ on a tracer that is not new | raise;
recorded".  Exam leftover check: "_ACTIVE == 0".

Run: PYTHONPATH=/home/user/styxx-1 python f08_reentry_race.py
"""
import importlib
import json
import subprocess
import sys
import tempfile
import textwrap
import threading
from pathlib import Path

from styxx.protocol import Experiment, GateSpecError, coverage_trace
import styxx.protocol as P


def make_exp(gates):
    td = Path(tempfile.mkdtemp(prefix="rt4lc_"))
    g = {k: {"metric": "m", "op": ">=", "value": 0.5, **v} for k, v in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {k: True for k in g}, "verdict": "PASS"},
                                     {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = td / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=td, check=True)
    return Experiment(p)


def make_mod(name, src):
    td = tempfile.mkdtemp(prefix="rt4lcmod_")
    Path(td, name + ".py").write_text(textwrap.dedent(src), encoding="utf-8")
    sys.path.insert(0, td)
    return importlib.import_module(name)


mod = make_mod("rt4lc_f08", """
    def a(x=0): return x + 1
    def b(x=0): return x + 2
    def c(x=0): return x + 3
    def d(x=0): return x + 4
""")
ORIG = mod.a.__code__
exp = make_exp({"G": {"exercises": [f"rt4lc_f08:{n}" for n in "abcd"]}})


def attempt():
    sys.modules.pop("rt4lc_f08", None)          # first trace of the run: target not imported yet
    importlib.invalidate_caches()
    COV = coverage_trace(exp)                  # one tracer object shared by the workers
    start = threading.Barrier(2)
    inside = threading.Barrier(2, timeout=5)
    out = {}

    def worker(i):
        start.wait()
        try:
            with COV:
                m = sys.modules["rt4lc_f08"]
                COV.run("G", lambda: (m.a(), m.b(), m.c(), m.d()))
                try:
                    inside.wait()              # both inside before either leaves
                except threading.BrokenBarrierError:
                    pass
            out[i] = "entered"
        except GateSpecError as e:
            out[i] = str(e)[:30]
            try:
                inside.abort()
            except Exception:  # noqa
                pass
    ths = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in ths:
        t.start()
    for t in ths:
        t.join()
    return COV, out


def reset():
    P._THREADS.clear(); P._ANCHORS.clear(); P._MINTED.clear(); P._BY_FN.clear()
    P._ACTIVE = 0
    sys.setprofile(None)


def main():
    for n in range(200):
        COV, out = attempt()
        if list(out.values()) == ["entered", "entered"]:
            rec = COV.record()
            calls = [o["calls"]["rt4lc_f08:a"] for o in rec["sections"]["G"]]
            active = P._ACTIVE
            try:
                verdict = exp.score({"m": 1.0, "coverage_trace": rec}).verdict
            except GateSpecError as e:
                verdict = str(e)[:95]
            print(f"FINDING-REPRODUCED: attempt {n}: two threads both entered one tracer object; "
                  f"no REENTRY anywhere; problems {[p[:20] for p in rec['problems']]} although no "
                  f"__code__ was replaced; target a called once per opening but recorded {calls}; "
                  f"_ACTIVE={active} after both with-blocks exited; score -> {verdict}")
            return
        reset()
    print("no finding: every attempt refused the second entry with REENTRY")


if __name__ == "__main__":
    main()
