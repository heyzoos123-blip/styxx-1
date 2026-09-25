# Variant: B (declaring Handle._run) is entered INSIDE a task step of a loop that runs in cov.run(A).
# The running Handle._run frame executes the original code while _STOP is B's mint.
import sys, os, asyncio
sys.path.insert(0, os.path.dirname(__file__))
import importlib.util
spec = importlib.util.spec_from_file_location("vr", os.path.join(os.path.dirname(__file__), "v_repro.py"))
# reuse helpers without running the battery: exec only the prelude part
src = open(os.path.join(os.path.dirname(__file__), "v_repro.py")).read().split("def x73_main")[0]
g = {"__file__": __file__}; exec(src, g)
EA, EB, verdict, vmod, P, coverage_trace = g["EA"], g["EB"], g["verdict"], g["vmod"], g["P"], g["coverage_trace"]

async def main_task():
    with coverage_trace(EB):
        vmod.f(9)            # runs in a task step (below the cut), while B is still active

with coverage_trace(EA) as a:
    a.run("A", asyncio.run, main_task())
print(sys.version.split()[0], "B-entered-inside-task-step ->", verdict(EA, a.record()))
