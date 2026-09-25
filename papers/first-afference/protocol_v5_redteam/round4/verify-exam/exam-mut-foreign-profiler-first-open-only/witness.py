"""A later open on a thread that already holds an open opening, under a foreign profiler."""
import asyncio, sys
import b6lib as W
mod = W.module("b6fp_fx", "def f():\n    return 1\ndef g():\n    return 2\n")

def foreign(frame, event, arg):                 # a pure-Python profiler, e.g. a user's own
    return None

def attempt(cov, section, fn):
    try:
        cov.run(section, fn)
        return "opened"
    except W.GateSpecError as e:
        return str(e)[:22]

out = {}
# (i) two tracers: outer section open on this thread, profiler started inside it, inner tracer opens.
e1 = W.experiment({"S1": {"exercises": ["b6fp_fx:g"]}}, tag="fp1o")
e2 = W.experiment({"S2": {"exercises": ["b6fp_fx:f"]}}, tag="fp1i")
t2 = W.coverage_trace(e2)
with W.coverage_trace(e1) as t1:
    def s1():
        mod.g()
        with t2:
            sys.setprofile(foreign)
            r = attempt(t2, "S2", mod.f)
            sys.setprofile(None)
        return r
    out["i_open_S2"] = t1.run("S1", s1)
out["i_inner_score"] = W.score(e2, t2.record())
out["i_inner_problems"] = [p[:22] for p in t2.record()["problems"]]

# (ii) as (i), but S2 was already opened once cleanly: the spec refuses the whole trace.
e3 = W.experiment({"S1": {"exercises": ["b6fp_fx:g"]}}, tag="fp2o")
e4 = W.experiment({"S2": {"exercises": ["b6fp_fx:f"]}}, tag="fp2i")
t4 = W.coverage_trace(e4)
with t4:
    t4.run("S2", mod.f)                         # clean opening, f credited
    with W.coverage_trace(e3) as t3:
        def s1b():
            mod.g()
            sys.setprofile(foreign)
            r = attempt(t4, "S2", mod.f)        # second opening, under the foreign profiler
            sys.setprofile(None)
            return r
        out["ii_open_S2_again"] = t3.run("S1", s1b)
out["ii_inner_score"] = W.score(e4, t4.record())

# (iii) one tracer, two asyncio tasks on one loop; task a starts a profiler before B opens.
e5 = W.experiment({"A": {"exercises": ["b6fp_fx:g"]}, "B": {"exercises": ["b6fp_fx:f"]}}, tag="fp3")
errs = []
async def a():
    mod.g()
    sys.setprofile(foreign)
    await asyncio.sleep(0)
    await asyncio.sleep(0)
async def b():
    mod.f()
async def safe(c):
    try:
        await c
    except W.GateSpecError as e:
        errs.append(str(e)[:22])
with W.coverage_trace(e5) as t5:
    async def main():
        await asyncio.gather(safe(t5.run_async("A", a)), safe(t5.run_async("B", b)))
    asyncio.run(main())
    sys.setprofile(None)
out["iii_open_errors"] = errs
out["iii_score"] = W.score(e5, t5.record())
out["state_at_end"] = W.globals_state()
W.emit(out)
