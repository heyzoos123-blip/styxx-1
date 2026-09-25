"""Lifecycle / interrupted __exit__ before its first statement: the tracer stays "active" for ever.

__exit__ begins `with _LOCK: if self._state != "active": ...; self._state = "exiting"; _ACTIVE -= 1`.
An asynchronous exception that lands on __exit__'s entry (RESUME) or on the `with _LOCK` call is
raised BEFORE the state changes, so:
  * record() refuses [V5:TRACE_ACTIVE] "take it after the trace exits" -- the spec says an
    interrupted exit leaves the state `exiting` and record() refuses TRACE_INCOMPLETE;
  * _ACTIVE is never decremented: it stays >= 1 after every later tracer has exited, for the rest
    of the process, so `_ACTIVE == 0` never holds again (exit step 5 never removes the hook,
    `_STOP` is never cleared, and the hook's `not _ACTIVE` self-removal never fires);
  * the interrupted tracer keeps accepting cov.run() after its with-block has ended.

Spec: "If an exception interrupts exit, the state stays `exiting` and `record()` refuses
**TRACE_INCOMPLETE**."  Stated limits: "Interrupted exit. It yields TRACE_INCOMPLETE and may leave
minted code installed (equal code)."

Run: PYTHONPATH=/home/user/styxx-1 python f04_interrupted_exit_stays_active.py
"""
import importlib
import json
import random
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
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


mod = make_mod("rt4lc_f04", """
    def work(x=0):
        return x + 1
""")
ORIG = mod.work.__code__
exp = make_exp({"G": {"exercises": ["rt4lc_f04:work"]}})


class Timeout(Exception):
    pass


ARMED = [False]


def handler(signum, frame):
    if ARMED[0]:
        raise Timeout()


def reset():                      # between samples only, so the sweep can keep looking
    P._THREADS.clear(); P._ANCHORS.clear(); P._MINTED.clear(); P._BY_FN.clear()
    P._ACTIVE = 0
    mod.work.__code__ = ORIG
    sys.setprofile(None)


def main(budget=45.0):
    signal.signal(signal.SIGALRM, handler)
    rnd = random.Random(11)
    end = time.monotonic() + budget
    while time.monotonic() < end:
        cov = None
        exited_body = [False]
        try:
            try:
                ARMED[0] = True
                signal.setitimer(signal.ITIMER_REAL, rnd.uniform(0.00002, 0.0004))
                with coverage_trace(exp) as cov:
                    cov.run("G", mod.work, 1)
                    exited_body[0] = True
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                ARMED[0] = False
        except (Timeout, GateSpecError):
            pass
        # only the shape we want: the body completed, the with statement then raised in __exit__
        # before __exit__ changed anything
        if not (cov is not None and exited_body[0] and cov._state == "active"
                and not P._THREADS and not P._ANCHORS):
            reset()
            continue
        try:
            cov.record()
            rec_code = "record() returned"
        except GateSpecError as e:
            rec_code = str(e)[:90]
        # three later, clean cases
        for _ in range(3):
            with coverage_trace(exp) as c2:
                c2.run("G", mod.work, 1)
            exp.score({"m": 1.0, "coverage_trace": c2.record()})
        active_after = P._ACTIVE
        still_opens = cov.run("G", mod.work, 5)       # the dead trace still opens sections
        if rec_code.startswith("[V5:TRACE_ACTIVE]") and active_after >= 1:
            print(f"FINDING-REPRODUCED: an exception on __exit__'s entry left the tracer "
                  f"'{cov._state}' (not 'exiting'): its record() refuses {rec_code!r}; after 3 "
                  f"later tracers entered and exited cleanly, styxx.protocol._ACTIVE is still "
                  f"{active_after} (never returns to 0); the exited-with tracer still runs "
                  f"sections (returned {still_opens})")
            return
        reset()
    print("no finding: no exit interrupted before its state change")


if __name__ == "__main__":
    main()
