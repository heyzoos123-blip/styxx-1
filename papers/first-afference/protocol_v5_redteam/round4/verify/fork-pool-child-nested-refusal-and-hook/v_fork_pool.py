"""Verifier's own repro for fork-pool-child-nested-refusal-and-hook.

Default ProcessPoolExecutor (no explicit context: fork on Linux 3.10-3.13).
  C1  workers forked from inside section A (pool created inside A); job does cov.run("B", g)
  C2  control: workers forked inside the trace but BEFORE A opens (warm-up); same job
  C3  control: ThreadPoolExecutor inside A; same job (the spec's remedy, V21 shape)
  C4  hook persistence: pool forked inside A outlives the parent tracer; probe the idle worker
  C5  multiprocessing.Pool (default ctx) created inside A; same job
Prints a JSON summary on the last line.
"""
import json, os, subprocess, sys, tempfile, time, warnings
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, "/home/user/styxx-1")
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace

warnings.simplefilter("ignore", DeprecationWarning)   # 3.12+: fork() with threads warning

HERE = Path(__file__).resolve().parent
FIX = Path(tempfile.mkdtemp(prefix="vfx_", dir=HERE))
(FIX / "vfp_fix.py").write_text("def f():\n    return 1\n\ndef g():\n    return 2\n\ndef h(n):\n    s = 0\n    for i in range(n):\n        s += _one(i)\n    return s\n\ndef _one(i):\n    return i & 1\n")
sys.path.insert(0, str(FIX))
import vfp_fix


def mkexp():
    td = Path(tempfile.mkdtemp(prefix="vexp_", dir=HERE))
    gates = {"A": {"metric": "a", "op": ">=", "value": 0.5, "exercises": ["vfp_fix:f"]},
             "B": {"metric": "b", "op": ">=", "value": 0.5, "exercises": ["vfp_fix:g"]}}
    spec = {"gates": gates,
            "outcomes": [{"when": {"A": True, "B": True}, "verdict": "PASS"},
                         {"when": {}, "verdict": "FAIL"}],
            "smoke_verdict": "S"}
    p = td / "PREREG_vfp.md"
    p.write_text("# vfp\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=v@v", "-c", "user.name=v", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=td, check=True)
    return Experiment(p)


COV = None


def job(i):
    # the spec's remedy for executors: the submitted function opens its own section
    return COV.run("B", vfp_fix.g)


def probe(_):
    return {"pid": os.getpid(), "getprofile": repr(sys.getprofile()),
            "is_hook": sys.getprofile() is P._hook, "_ACTIVE": P._ACTIVE,
            "_THREADS": len(P._THREADS), "_ANCHORS": len(P._ANCHORS),
            "g_code_minted": id(vfp_fix.g.__code__) in P._MINTED}


def timed_work(_):
    t = time.perf_counter()
    vfp_fix.h(300000)
    return time.perf_counter() - t


def collect(futs):
    out = []
    for fu in futs:
        try:
            out.append(("ok", fu.result(timeout=30)))
        except GateSpecError as e:
            out.append(("GateSpecError", str(e)[:110]))
        except Exception as e:  # noqa
            out.append((type(e).__name__, str(e)[:110]))
    return out


def score_both(exp, rec):
    res = {"a": 1.0, "b": 1.0, "coverage_trace": rec}
    out = {}
    for n in ("A", "B"):
        try:
            out[n] = exp._check_coverage(n, res)
        except GateSpecError as e:
            out[n] = str(e)[:70]
    return out


def main():
    global COV
    exp = mkexp()
    summary = {"python": sys.version.split()[0], "start_method": mp.get_start_method()}

    # C1: pool created and first used inside A
    with coverage_trace(exp) as cov:
        COV = cov
        box = {}

        def gate_a():
            vfp_fix.f()
            with ProcessPoolExecutor(2) as ex:
                box["jobs"] = collect([ex.submit(job, i) for i in range(2)])
        cov.run("A", gate_a)
    rec = cov.record()
    summary["C1_jobs"] = box["jobs"]
    summary["C1_parent_problems"] = rec["problems"]
    summary["C1_parent_sections"] = rec["sections"]
    summary["C1_scores"] = score_both(exp, rec)
    summary["C1_parent_leftovers"] = [P._ACTIVE, len(P._THREADS), len(P._ANCHORS),
                                      len(P._MINTED), repr(sys.getprofile())]

    # C2: control -- workers forked inside the trace, before A opens
    with coverage_trace(exp) as cov:
        COV = cov
        with ProcessPoolExecutor(2) as ex:
            ex.submit(int, 0).result(timeout=30)       # forks both workers here, outside A
            box = {}

            def gate_a2():
                vfp_fix.f()
                box["jobs"] = collect([ex.submit(job, i) for i in range(2)])
            cov.run("A", gate_a2)
    rec = cov.record()
    summary["C2_jobs"] = box["jobs"]
    summary["C2_scores"] = score_both(exp, rec)

    # C3: control -- ThreadPoolExecutor inside A (V21 shape)
    with coverage_trace(exp) as cov:
        COV = cov
        box = {}

        def gate_a3():
            vfp_fix.f()
            with ThreadPoolExecutor(2) as ex:
                box["jobs"] = collect([ex.submit(job, i) for i in range(2)])
        cov.run("A", gate_a3)
    rec = cov.record()
    summary["C3_jobs"] = box["jobs"]
    summary["C3_scores"] = score_both(exp, rec)

    # C4: pool forked inside A outlives the parent's tracer; probe an idle worker afterwards
    ex = ProcessPoolExecutor(1)
    with coverage_trace(exp) as cov:
        COV = cov
        cov.run("A", lambda: (vfp_fix.f(), ex.submit(int, 0).result(timeout=30)))
    summary["C4_parent_getprofile_after_exit"] = repr(sys.getprofile())
    summary["C4_worker_probe_after_parent_exit"] = ex.submit(probe, 0).result(timeout=30)
    t_hooked = min(ex.submit(timed_work, 0).result(timeout=30) for _ in range(3))
    ex.shutdown()
    ex2 = ProcessPoolExecutor(1)                         # clean worker, forked with no tracer
    summary["C4_clean_worker_probe"] = ex2.submit(probe, 0).result(timeout=30)
    t_clean = min(ex2.submit(timed_work, 0).result(timeout=30) for _ in range(3))
    ex2.shutdown()
    summary["C4_worker_time_hooked_s"] = round(t_hooked, 4)
    summary["C4_worker_time_clean_s"] = round(t_clean, 4)

    # C5: multiprocessing.Pool created inside A
    with coverage_trace(exp) as cov:
        COV = cov
        box = {}

        def gate_a5():
            vfp_fix.f()
            with mp.Pool(2) as pool:
                ars = [pool.apply_async(job, (i,)) for i in range(2)]
                r = []
                for a in ars:
                    try:
                        r.append(("ok", a.get(timeout=30)))
                    except Exception as e:  # noqa
                        r.append((type(e).__name__, str(e)[:110]))
                box["jobs"] = r
        cov.run("A", gate_a5)
    rec = cov.record()
    summary["C5_jobs"] = box["jobs"]
    summary["C5_parent_problems"] = rec["problems"]

    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()
