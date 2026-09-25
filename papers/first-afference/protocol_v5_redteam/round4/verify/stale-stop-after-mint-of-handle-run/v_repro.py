# Independent verifier repro: a tracer that declares asyncio.events:Handle._run leaves _STOP stale.
import json, os, subprocess, sys, tempfile, textwrap, threading, asyncio, asyncio.events
from pathlib import Path
sys.path.insert(0, os.environ.get("STYXX_ROOT", "/home/user/styxx-1"))
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace

tmp = Path(tempfile.mkdtemp(prefix="vstale_"))
(tmp / "vmod.py").write_text("def f(x=0):\n    return x\n")
sys.path.insert(0, str(tmp))
import vmod

def exp_for(gates):
    d = Path(tempfile.mkdtemp(prefix="vstale_repo_"))
    g = {k: {"metric": "m", "op": ">=", "value": 0.5, **v} for k, v in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {k: True for k in g}, "verdict": "PASS"},
                                     {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = d / "PREREG_v.md"
    p.write_text("# v\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=d, check=True)
    return Experiment(p)

EA = exp_for({"A": {"exercises": ["vmod:f"]}})
EB = exp_for({"B": {"exercises": ["asyncio.events:Handle._run"]}})

def verdict(exp, rec):
    try:
        v = exp.score({"m": 1.0, "coverage_trace": rec})
        return "PASS " + json.dumps(v.coverage)
    except GateSpecError as e:
        return "REFUSED " + str(e)[:60] + " | uncredited=" + json.dumps(rec["uncredited"])

# X73 shape: loop inside cov.run, f only in gathered child tasks
def x73_main():
    async def child():
        vmod.f(1)
    async def m():
        await asyncio.gather(child(), child())
    return m()

# X65/J1-X2 shape: loop inside cov.run(A); an UNSECTIONED other thread submits f via
# run_coroutine_threadsafe and call_soon_threadsafe. f runs only in those jobs.
def x65_body():
    async def job():
        vmod.f(2)
    async def m():
        loop = asyncio.get_running_loop()
        done = asyncio.Event()
        def submitter():
            fut = asyncio.run_coroutine_threadsafe(job(), loop)
            fut.result(10)
            loop.call_soon_threadsafe(vmod.f, 3)
            loop.call_soon_threadsafe(done.set)
        t = threading.Thread(target=submitter); t.start()
        await done.wait()
        t.join()
    asyncio.run(m())

def inner_lifo():
    with coverage_trace(EB):
        pass

def run(shape, perturb):
    if perturb == "nonlifo":
        b = coverage_trace(EB); b.__enter__()
        a = coverage_trace(EA); a.__enter__()
        b.__exit__(None, None, None)
    else:
        a = coverage_trace(EA); a.__enter__()
        if perturb == "lifo":
            inner_lifo()
        elif perturb == "thread":           # a concurrent tracer on another thread, entered/exited
            t = threading.Thread(target=inner_lifo); t.start(); t.join()
    live = P._STOP is asyncio.events.Handle._run.__code__
    if shape == "x73":
        a.run("A", asyncio.run, x73_main())
    else:
        a.run("A", x65_body)
    a.__exit__(None, None, None)
    return f"{shape:4} {perturb:8} _STOP live={live!s:5} -> {verdict(EA, a.record())}"

orig = asyncio.events.Handle._run.__code__
print(sys.version.split()[0])
for shape in ("x73", "x65"):
    for perturb in ("none", "lifo", "nonlifo", "thread"):
        print(run(shape, perturb))
print("restored:", asyncio.events.Handle._run.__code__ is orig, "active", P._ACTIVE, "stop", P._STOP,
      "minted", len(P._MINTED), "prof", sys.getprofile())
