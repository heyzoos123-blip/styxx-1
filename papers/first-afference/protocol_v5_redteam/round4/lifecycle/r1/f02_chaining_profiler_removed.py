"""Lifecycle / foreign profiler: the styxx hook's self-removal uninstalls a user's profiler.

_hook's first branch is `if not _ACTIVE or tid not in _THREADS: sys.setprofile(None)`.  It never
checks that it IS the installed profile function.  A user profiler that politely chains to the
profiler it found (prev = sys.getprofile(); call prev(frame, event, arg) from its own callback) is
the installed profiler, and styxx's hook is only being CALLED by it.  As soon as the section closes
(or the trace exits), the next event the user's profiler forwards makes styxx's hook run
sys.setprofile(None) -- which removes the USER's profiler from the thread.  Their profiler silently
stops receiving events; nothing is raised or noted.

The spec: "The foreign profiler is never called, chained, restored or replaced." (At open.)
          "Kept ... settrace tools ... unaffected"; "R3 nit: Ctrl-C drops a chained profiler |
           CLOSED_S | Nothing is chained; a foreign profiler ... is left untouched".
and _close deliberately leaves a non-styxx profiler installed ("if ... sys.getprofile() is _hook:
sys.setprofile(None)").  The hook's own self-removal has no such guard.

Harness shape: the author profiles one phase of a section with a small chaining profiler
(e.g. a call counter that forwards to whatever profiler was there, so it composes with others).

Run: PYTHONPATH=/home/user/styxx-1 python f02_chaining_profiler_removed.py
"""
import importlib
import json
import subprocess
import sys
import tempfile
import textwrap
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


mod = make_mod("rt4lc_f02", """
    def work(x=0):
        return x + 1
    def later(x=0):
        return x * 2
""")
exp = make_exp({"G": {"exercises": ["rt4lc_f02:work"]}})


class ChainingCounter:
    """A user profiler that counts Python calls and forwards to whatever profiler was installed."""
    def __init__(self):
        self.calls = 0
        self.prev = None

    def __call__(self, frame, event, arg):
        if event == "call":
            self.calls += 1
        if self.chain and self.prev is not None:
            self.prev(frame, event, arg)

    def start(self):
        self.prev = sys.getprofile()
        sys.setprofile(self)


def run_once(chain):
    prof = ChainingCounter()
    prof.chain = chain

    def section_body():
        prof.start()       # started inside the section: styxx's hook is the profiler it finds
        mod.work(1)
    with coverage_trace(exp) as cov:
        cov.run("G", section_body)
        # the section is closed; the user's profiler should still be installed and counting
        after_close = sys.getprofile()
        before = prof.calls
        for i in range(5):
            mod.later(i)
        counted = prof.calls - before
    rec = cov.record()
    sys.setprofile(None)
    try:
        verdict = exp.score({"m": 1.0, "coverage_trace": rec}).verdict
    except GateSpecError as e:
        verdict = str(e)[:60]
    notes = [n[:26] for s in rec["sections"].values() for o in s for n in o["notes"]]
    return after_close is prof, counted, verdict, notes


def main():
    ctl = run_once(chain=False)     # control: a non-chaining profiler is left installed by _close
    bug = run_once(chain=True)
    if ctl[0] and ctl[1] == 5 and not bug[0] and bug[1] == 0:
        print(f"FINDING-REPRODUCED: a user profiler started inside a section survives the close "
              f"when it does not chain (control: installed, 5/5 calls seen), but when it forwards "
              f"to the profiler it found (styxx's hook), the hook's self-removal "
              f"sys.setprofile(None) uninstalls it at the close: installed={bug[0]}, "
              f"{bug[1]}/5 later calls seen (verdict {bug[2]}, notes {bug[3]})")
    else:
        print(f"no finding: control={ctl} chaining={bug}")


if __name__ == "__main__":
    main()
