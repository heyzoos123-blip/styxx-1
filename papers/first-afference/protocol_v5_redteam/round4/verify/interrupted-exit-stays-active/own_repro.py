"""Verifier's own repro for 'interrupted-exit-stays-active'.

Claim: an exception that lands on _CoverageTracer.__exit__'s entry (before `with _LOCK:` and the
state change) leaves the tracer 'active', so record() refuses TRACE_ACTIVE (not TRACE_INCOMPLETE as
the spec says for an interrupted exit), and _ACTIVE is never decremented.

Modes (each in a fresh process, no reset of module state anywhere):
  entry-profiler : deterministic, X92-style. A profiler raises at the 'call' event of __exit__
                   itself (X92 raises at the c_call of sys.getrefcount inside the exit instead).
  entry-signal   : realistic. A repeating SIGALRM whose handler raises only when the frame it
                   interrupts is __exit__ with self._state still 'active' (i.e. __exit__'s entry).
  mid-profiler   : contrast = the spec's documented case (X92's own injection point).
"""
import importlib
import json
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import traceback
from pathlib import Path

import styxx.protocol as P
from styxx.protocol import GateSpecError, Experiment, coverage_trace

EXIT_CODE = P._CoverageTracer.__exit__.__code__
_GETREFCOUNT = sys.getrefcount


def make_exp():
    td = Path(tempfile.mkdtemp(prefix="v_iesa_"))
    spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5,
                            "exercises": ["v_iesa_mod:work"]}},
            "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
            "smoke_verdict": "S"}
    p = td / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=td, check=True)
    return Experiment(p)


td = tempfile.mkdtemp(prefix="v_iesa_mod_")
Path(td, "v_iesa_mod.py").write_text("def work(x=0):\n    return x + 1\n", encoding="utf-8")
sys.path.insert(0, td)
mod = importlib.import_module("v_iesa_mod")
ORIG = mod.work.__code__
exp = make_exp()


class Injected(Exception):
    pass


def innermost(tb):
    chain = []
    while tb is not None:
        chain.append(f"{tb.tb_frame.f_code.co_name}:{tb.tb_lineno}")
        tb = tb.tb_next
    return " > ".join(chain)


def report(cov, where):
    out = {"py": sys.version.split()[0], "raised_in": where, "state_after_with": cov._state}
    try:
        cov.record()
        out["record"] = "returned"
    except GateSpecError as e:
        out["record"] = str(e)
    out["_ACTIVE_after_with"] = P._ACTIVE
    out["_STOP_set"] = P._STOP is not None
    out["code_still_minted"] = mod.work.__code__ is not ORIG
    verdicts = []
    for _ in range(3):
        with coverage_trace(exp) as c2:
            c2.run("G", mod.work, 1)
        verdicts.append(exp.score({"m": 1.0, "coverage_trace": c2.record()}).verdict)
    out["later_clean_verdicts"] = verdicts
    out["_ACTIVE_after_3_clean_tracers"] = P._ACTIVE
    out["_MINTED_len"] = len(P._MINTED)
    # the with block is over; does the old tracer still open sections and credit calls?
    try:
        r = cov.run("G", mod.work, 5)
        out["dead_tracer_run"] = f"returned {r}; openings={len(cov._openings)}; " \
                                 f"last calls={cov._openings[-1].calls}"
    except GateSpecError as e:
        out["dead_tracer_run"] = str(e)
    # a harness hook left outside any section: does self-removal still work with _ACTIVE leaked?
    sys.setprofile(P._hook)
    mod.work(0)
    out["hook_after_one_event_outside_sections"] = repr(sys.getprofile())
    sys.setprofile(None)
    print(json.dumps(out, indent=1))


def mode_entry_profiler():
    def fault(frame, event, arg):
        if event == "call" and frame.f_code is EXIT_CODE:
            raise Injected("fault at __exit__'s call event")
    cov = None
    try:
        with coverage_trace(exp) as cov:
            cov.run("G", mod.work, 1)
            sys.setprofile(fault)          # installed after the last close, like X92
    except Injected as e:
        sys.setprofile(None)
        report(cov, innermost(e.__traceback__))
        return
    sys.setprofile(None)
    print("NOT REPRODUCED: exit completed")


def mode_mid_profiler():
    def fault(frame, event, arg):
        if event == "c_call" and arg is _GETREFCOUNT:
            raise Injected("fault at sys.getrefcount inside exit")
    cov = None
    try:
        with coverage_trace(exp) as cov:
            cov.run("G", mod.work, 1)
            sys.setprofile(fault)
    except Injected as e:
        sys.setprofile(None)
        report(cov, innermost(e.__traceback__))
        return
    sys.setprofile(None)
    print("NOT REPRODUCED: exit completed")


def mode_entry_signal(budget=30.0):
    hits = {"n": 0}

    def handler(signum, frame):
        if frame is not None and frame.f_code is EXIT_CODE:
            self_ = frame.f_locals.get("self")
            if self_ is not None and self_._state == "active":
                hits["n"] += 1
                raise Injected(f"SIGALRM at __exit__ entry (f_lasti={frame.f_lasti})")

    signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, 0.00005, 0.00005)
    end = time.monotonic() + budget
    i = 0
    try:
        while time.monotonic() < end:
            i += 1
            cov = None
            try:
                with coverage_trace(exp) as cov:
                    cov.run("G", mod.work, 1)
            except Injected as e:
                signal.setitimer(signal.ITIMER_REAL, 0, 0)
                print(f"hit after {i} iterations: {e}; innermost frame: "
                      f"{innermost(e.__traceback__)}")
                report(cov, innermost(e.__traceback__))
                return
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0, 0)
    print(f"NOT REPRODUCED in {i} iterations")


if __name__ == "__main__":
    {"entry-profiler": mode_entry_profiler, "mid-profiler": mode_mid_profiler,
     "entry-signal": mode_entry_signal}[sys.argv[1]]()
