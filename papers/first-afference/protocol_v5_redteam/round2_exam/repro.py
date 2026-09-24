import sys, json, asyncio, threading, tempfile, subprocess
from pathlib import Path
sys.path.insert(0, sys.argv[1] + "/fx")
from styxx.protocol import Experiment, GateSpecError, coverage_trace
import _rtfx as fx
T, A = "_rtfx:target", "_rtfx:alias"
def exp(spec):
    d = Path(tempfile.mkdtemp()); p = d / "PREREG_x.md"
    p.write_text("# x\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git","init","-q"],["git","add","-A"],["git","-c","user.email=a@b","-c","user.name=a","commit","-qm","x"]):
        subprocess.run(c, cwd=d, check=True)
    return Experiment(p)
def spec(**g):
    gg = {n: {"metric":"m","op":">=","value":0.5, **e} for n,e in g.items()}
    return {"gates": gg, "outcomes":[{"when":{n:True for n in gg},"verdict":"PASS"},{"when":{},"verdict":"FAIL"}], "smoke_verdict":"S"}
def run(name, f):
    try: print(name, "->", f())
    except GateSpecError as e: print(name, "-> REFUSED", str(e)[:90])
    except Exception as e: print(name, "-> CRASH", type(e).__name__, str(e)[:90])

def after_close():   # target called only after G closed (task created in G, awaited outside)
    e = exp(spec(G={"exercises":[T]}))
    with coverage_trace(e) as cov:
        async def work(): await asyncio.sleep(0); fx.target()
        async def main():
            with cov.section("G"): t = asyncio.ensure_future(work())
            await t
        asyncio.run(main())
    r = {"m":1.0, "coverage_trace": cov.record()}
    return e.score(r).verdict, r["coverage_trace"]["sections"], r["coverage_trace"]["after_close"]
run("R06 call only after its section closed", after_close)

def alias2():
    e = exp(spec(G={"exercises":[T]}, H={"exercises":[A]}))
    with coverage_trace(e) as cov:
        with cov.section("G"): fx.target()
        with cov.section("H"): fx.target()
    return e.score({"m":1.0, "coverage_trace": cov.record()}).verdict
run("R02b two declared targets, one function (alias)", alias2)

def base():
    e = exp(spec(G={"exercises":[T]}))
    with coverage_trace(e) as cov:
        with cov.section("G"): fx.target()
    return e, {"m":1.0, "coverage_trace": cov.record()}
def sec_key():
    e, r = base(); r["coverage_trace"]["sections"][7] = {}; return e.score(r).verdict
run("R13b non-string key in sections (top level)", sec_key)
def sec_inner_key():
    e, r = base(); r["coverage_trace"]["sections"]["G"][7] = 1; return e.score(r).verdict
run("R13c non-string key inside a section", sec_inner_key)
def sec_list():
    e, r = base(); r["coverage_trace"]["sections"]["G"] = [T]; return e.score(r).verdict
run("R13c section value is a list", sec_list)
def cm_sec_list():
    e, r = base(); r["coverage_trace"]["sections"]["G"] = [T]; return e.check_metrics(r)["G:exercises"]
run("R13c check_metrics on a list section", cm_sec_list)
def cm_bad():
    e, r = base(); r["coverage_trace"]["targets"][None] = "x"; return e.check_metrics(r)["G:exercises"]["usable"]
run("R13d check_metrics with non-string key", cm_bad)
def missing_target():
    e, r = base(); r["coverage_trace"]["targets"] = {}; r["coverage_trace"]["sections"]["G"] = {}
    return e.score(r).verdict
run("TARGET_SET trace lacks a declared target", missing_target)
def undeclared_key_in_sec():
    e, r = base(); r["coverage_trace"]["sections"]["G"]["_rtfx:zzz"] = 1; return e.score(r).verdict
run("BAD_COUNT undeclared name in section", undeclared_key_in_sec)
def nonascii():
    return exp(spec(G={"exercises":["_rtfx:targét"]})).coverage
run("R14b non-ASCII target", nonascii)
def reuse_after_exit():
    e = exp(spec(G={"exercises":[T]}))
    cov = coverage_trace(e)
    with cov: pass
    with cov:
        with cov.section("G"): fx.target()
    return e.score({"m":1.0,"coverage_trace":cov.record()}).verdict
run("R10b re-enter an exited tracer", reuse_after_exit)
def grandchild_thread():
    e = exp(spec(G={"exercises":[T]}))
    with coverage_trace(e) as cov:
        def outer():
            th = threading.Thread(target=fx.target); th.start(); th.join()
        with cov.section("G"):
            th = threading.Thread(target=outer); th.start(); th.join()
    return e.score({"m":1.0,"coverage_trace":cov.record()}).verdict
run("R05b thread started from a thread started in section", grandchild_thread)
