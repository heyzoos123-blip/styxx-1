"""Independent repro for py310-hook-reverts-closure-writes.

A: deterministic, single thread. A local is dropped with `del`; a Python helper then observes whether
   its finalizer has run. Compared untraced, inside cov.run(), and under a bare Python-level
   sys.setprofile(no-op) control (to show the CPython root cause).
B: a worker thread increments a nonlocal counter that only it writes; the opener thread only reads.
C: a worker sets a nonlocal flag once; the opener spin-waits with a deadline; afterwards we check
   whether the flag is STILL False after the worker has exited (i.e. a permanent revert -> a hang
   without the deadline).
Run: PYTHONPATH=/home/user/styxx-1 <python> own_repro.py
"""
import json, os, subprocess, sys, tempfile, threading, time
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="v_py310_"))
mod = "_v_py310_mod"
(tmp / f"{mod}.py").write_text("def tgt():\n    return 1\n")
sys.path.insert(0, str(tmp))
repo = tmp / "repo"; repo.mkdir()
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": [f"{mod}:tgt"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "S"}
p = repo / "PREREG_v.md"
p.write_text("# v\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false",
             "commit", "-qm", "c"]):
    subprocess.run(cmd, cwd=repo, check=True)

from styxx.protocol import Experiment, coverage_trace
import importlib
m = importlib.import_module(mod)
exp = Experiment(p)

log = []
class Res:
    def __del__(self):
        log.append("finalized")

def observe():                      # a plain Python helper: its 'call' event is on ITS frame
    return list(log)

def case_a():
    log.clear()
    r = Res()
    len(log)                        # any C call on this frame (a c_call event on 3.10 snapshots r)
    del r                           # CPython: last ref gone -> __del__ runs here
    seen = observe()
    m.tgt()
    return seen

def case_b(N=200_000):
    counter = 0
    def worker():
        nonlocal counter
        for _ in range(N):
            counter += 1
    t = threading.Thread(target=worker); t.start()
    while t.is_alive():
        len(log)                    # the opener only reads; it never writes counter
    t.join()
    m.tgt()
    return N - counter

def case_c(trials=100, deadline=0.05):
    permanently_reverted = 0
    for _ in range(trials):
        done = False
        go = threading.Event()
        def worker():
            nonlocal done
            go.wait()
            done = True
        t = threading.Thread(target=worker); t.start()
        go.set()
        end = time.monotonic() + deadline
        while not done and time.monotonic() < end:
            len(log)
        t.join()                    # worker is gone; nobody writes done again
        time.sleep(0)
        if not done:
            permanently_reverted += 1
    m.tgt()
    return permanently_reverted

ver = sys.version.split()[0]
sys.setswitchinterval(float(os.environ.get("SWITCH", "0.005")))
res = {"ver": ver}
res["A_untraced"] = case_a()
res["B_untraced"] = case_b()
res["C_untraced"] = case_c()

with coverage_trace(exp) as cov:
    res["A_section"] = cov.run("G", case_a)
    res["B_section"] = cov.run("G", case_b)
    res["C_section"] = cov.run("G", case_c)
res["verdict"] = exp.score({"m": 1.0, "coverage_trace": cov.record()}).verdict
res["getprofile_after"] = repr(sys.getprofile())

# control: a bare Python-level profile function, no styxx
sys.setprofile(lambda f, e, a: None)
res["A_bare_py_profiler"] = case_a()
sys.setprofile(None)
print(json.dumps(res))
