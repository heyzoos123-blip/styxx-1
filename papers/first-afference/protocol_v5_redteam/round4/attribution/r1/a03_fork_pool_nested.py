"""ProcessPoolExecutor (fork start method, the Linux default on 3.10-3.13) spawns its workers
lazily from submit(), i.e. from the submitting thread's stack. Submitted inside cov.run("A"), each
forked worker's main thread is a COPY of the section's stack, with the profile hook installed and
A's anchor registered in its copied _ANCHORS. A job that opens its own section -- the spec's
remedy for pools ("each job opens its own section, with cov.run inside the submitted function")
-- raises [V5:NESTED_SECTION] in the child, which reaches the parent through future.result().
The parent's trace records no problem at all; the message ("opened on the stack of an open
opening of section 'A' of the same trace") describes a stack that exists only in the child's
copy. Over-blocking #15 says only "Child processes are invisible"."""
import json, subprocess, sys, tempfile, os
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
sys.path.insert(0, "/home/user/styxx-1")
from styxx.protocol import Experiment, GateSpecError, coverage_trace

FIX = Path(tempfile.mkdtemp(prefix="a03fx_"))
(FIX / "a03_fix.py").write_text("def f(): return 1\ndef g(): return 2\n")
sys.path.insert(0, str(FIX))
import a03_fix

def mkexp(gates):
    td = Path(tempfile.mkdtemp(prefix="a03_"))
    g = {n: {"metric": "m", "op": ">=", "value": 0.5, **x} for n, x in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {n: True for n in g}, "verdict": "PASS"},
                                     {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = td / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=td, check=True)
    return Experiment(p)

COV = None

def job(i):
    # the job opens its own section, as the spec's remedy for pools says
    COV.run("B", a03_fix.g)
    return (os.getpid(), sys.getprofile() is not None)

def probe(i):
    return (os.getpid(), repr(sys.getprofile()))

if __name__ == "__main__":
    exp = mkexp({"A": {"exercises": ["a03_fix:f"]}, "B": {"exercises": ["a03_fix:g"]}})
    ctx = mp.get_context("fork")
    out = {}
    with coverage_trace(exp) as cov:
        COV = cov
        with ProcessPoolExecutor(2, mp_context=ctx) as ex:
            def gate_a():
                a03_fix.f()
                futs = [ex.submit(job, i) for i in range(2)]
                res = []
                for fu in futs:
                    try:
                        res.append(fu.result(timeout=30))
                    except GateSpecError as e:
                        res.append(f"GateSpecError {str(e)[:100]}")
                    except Exception as e:
                        res.append(f"{type(e).__name__} {str(e)[:100]}")
                out["jobs"] = res
                out["probe"] = ex.submit(probe, 0).result(timeout=30)
            cov.run("A", gate_a)
    rec = cov.record()
    print("  job results in parent:", out["jobs"])
    print("  a worker's sys.getprofile() while idle in the pool:", out["probe"])
    print("  parent trace problems:", rec["problems"])
    nested = [r for r in out["jobs"] if isinstance(r, str) and "NESTED_SECTION" in r]
    if nested and not rec["problems"]:
        print("FINDING-REPRODUCED: a process-pool job that opens its own section raises "
              "NESTED_SECTION in the forked worker (parent trace records nothing); the pool "
              "was created and first used inside section A")
    else:
        print("no finding: process-pool jobs opening their own sections do not raise")
