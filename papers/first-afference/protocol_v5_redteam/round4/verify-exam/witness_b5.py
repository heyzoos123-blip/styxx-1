"""Batch-5 witness: run one scenario against the styxx under argv[1]; print a JSON outcome.

usage: python witness_b5.py <import_root> <scenario>
scenarios: nested_same_name, restore_swapped, close_foreign_prof, exit_foreign_prof_inside,
           exit_foreign_prof_preexisting
"""
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

sys.dont_write_bytecode = True
ROOT, SCEN = sys.argv[1], sys.argv[2]
sys.path.insert(0, ROOT)
import styxx.protocol as P                                       # noqa: E402
from styxx.protocol import Experiment, GateSpecError, coverage_trace   # noqa: E402

assert P.__file__.startswith(ROOT), P.__file__
WORK = Path(tempfile.mkdtemp(prefix="w5_"))
(WORK / "_w5_mod.py").write_text(
    "def f(): return 'v1'\n"
    "def g(): return 'g'\n"
    "def f_v2(): return 'v2'\n")
sys.path.insert(0, str(WORK))
import _w5_mod as M                                              # noqa: E402

_n = [0]


def exp_for(gates: dict) -> Experiment:
    """A committed prereg whose gates block declares *gates* ({name: [targets]})."""
    _n[0] += 1
    d = WORK / f"repo{_n[0]}"
    d.mkdir()
    g = {n: {"metric": "m", "op": ">=", "value": 0.5, "exercises": t} for n, t in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {n: True for n in g}, "verdict": "PASS"},
                                     {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "SMOKE"}
    p = d / "PREREG_w.md"
    p.write_text("# w\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=w@local", "-c", "user.name=w", "-c", "commit.gpgsign=false",
                 "commit", "-qm", "w"]):
        subprocess.run(cmd, cwd=d, check=True, capture_output=True)
    return Experiment(p)


def score(exp, rec):
    try:
        v = exp.score({"m": 1.0, "coverage_trace": rec})
        return f"{v.verdict}"
    except GateSpecError as e:
        return "REFUSED " + str(e)[:110]


def calls(rec):
    return {s: [o["calls"] for o in ops] for s, ops in rec["sections"].items()}


def clean_state():
    return {"profiler_none": sys.getprofile() is None,
            "registries_empty": not (P._MINTED or P._BY_FN or P._ANCHORS or P._THREADS),
            "_ACTIVE": P._ACTIVE}


out = {}
if SCEN == "nested_same_name":
    # a session-level tracer and a per-test tracer whose preregs both name their gate "G1"
    # (each prereg's own gate namespace; the spec: "Other tracers may nest, and each credits its
    # own openings")
    e_out = exp_for({"G1": ["_w5_mod:f"]})
    e_in = exp_for({"G1": ["_w5_mod:f"]})
    box = {}
    with coverage_trace(e_out) as outer:
        def body():
            with coverage_trace(e_in) as inner:
                try:
                    inner.run("G1", M.f)
                    box["inner_run"] = "ok"
                except GateSpecError as e:
                    box["inner_run"] = "RAISED " + str(e)[:90]
            box["inner"] = inner.record()
        outer.run("G1", body)
    out["inner_run"] = box["inner_run"]
    out["outer_calls"], out["inner_calls"] = calls(outer.record()), calls(box["inner"])
    out["outer_verdict"] = score(e_out, outer.record())
    out["inner_verdict"] = score(e_in, box["inner"])
elif SCEN == "restore_swapped":
    # a hot reload of f's code during the trace (the user's own program change)
    e = exp_for({"G": ["_w5_mod:f"]})
    orig = M.f.__code__
    with coverage_trace(e) as cov:
        def body():
            M.f()
            M.f.__code__ = M.f_v2.__code__      # hot reload: f now returns 'v2'
        cov.run("G", body)
    out["verdict"] = score(e, cov.record())
    out["f()_after_exit"] = M.f()
    out["f.__code___is_v2_code"] = M.f.__code__ is M.f_v2.__code__
    out["f.__code___is_pre_trace_code"] = M.f.__code__ is orig
elif SCEN == "close_foreign_prof":
    # a profiler the harness starts inside a section (a disclosed blinding, over-block #6)
    e = exp_for({"G": ["_w5_mod:f"]})
    hits = [0]

    def my_prof(frame, event, arg):
        hits[0] += 1
    with coverage_trace(e) as cov:
        def body():
            M.f()
            sys.setprofile(my_prof)
        cov.run("G", body)
        out["profiler_is_mine_after_close"] = sys.getprofile() is my_prof
        h0 = hits[0]
        M.g()
        out["my_prof_still_called_after_close"] = hits[0] > h0
    out["profiler_is_mine_after_exit"] = sys.getprofile() is my_prof
    sys.setprofile(None)
    rec = cov.record()
    out["notes"] = [n[:40] for ops in rec["sections"].values() for o in ops for n in o["notes"]]
    out["verdict"] = score(e, rec)
elif SCEN == "exit_foreign_prof_inside":
    # the harness installs its own profiler inside the with, after its sections closed
    e = exp_for({"G": ["_w5_mod:f"]})

    def my_prof(frame, event, arg):
        pass
    with coverage_trace(e) as cov:
        cov.run("G", M.f)
        sys.setprofile(my_prof)
    out["profiler_is_mine_after_exit"] = sys.getprofile() is my_prof
    sys.setprofile(None)
    out["verdict"] = score(e, cov.record())
elif SCEN == "exit_foreign_prof_preexisting":
    # a whole-program pure-Python profiler on the main thread BEFORE the trace; every section
    # runs on a worker thread that opens its own section (the documented pattern, V21)
    e = exp_for({"G": ["_w5_mod:f"]})
    hits = [0]

    def my_prof(frame, event, arg):
        hits[0] += 1
    sys.setprofile(my_prof)
    with coverage_trace(e) as cov:
        t = threading.Thread(target=cov.run, args=("G", M.f))
        t.start()
        t.join()
    out["profiler_is_mine_after_exit"] = sys.getprofile() is my_prof
    h0 = hits[0]
    M.g()
    out["my_prof_still_called_after_exit"] = hits[0] > h0
    sys.setprofile(None)
    out["verdict"] = score(e, cov.record())
else:
    raise SystemExit(f"unknown scenario {SCEN}")
out["state_after"] = clean_state()
print(json.dumps(out, sort_keys=True))
