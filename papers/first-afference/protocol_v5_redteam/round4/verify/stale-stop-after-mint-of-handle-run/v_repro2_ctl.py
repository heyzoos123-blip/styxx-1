import sys, os, asyncio
d = "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt4/verify/stale-stop-after-mint-of-handle-run"
src = open(os.path.join(d, "v_repro.py")).read().split("def x73_main")[0]
g = {}; exec(src, g)
EA, verdict, vmod, coverage_trace = g["EA"], g["verdict"], g["vmod"], g["coverage_trace"]
async def main_task():
    vmod.f(9)
with coverage_trace(EA) as a:
    a.run("A", asyncio.run, main_task())
print(sys.version.split()[0], "control (no B) ->", verdict(EA, a.record()))
