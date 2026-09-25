"""Witness: the attribution walk is cut only at asyncio's Handle._run code object, not at any
frame whose code is NAMED _run."""
import asyncio, json, sys
sys.path.insert(0, "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt4/verify-exam/examhole-dispatch-cut-by-name")
import witlib
P = witlib.load(sys.argv[1])
m = witlib.fixture("wd_fx", """
    def f(): return 1
""")
T = lambda n: f"wd_fx:{n}"
out = {}
def _run(cfg):                       # an ordinary harness helper that happens to be named _run
    return m.f() + cfg
e = witlib.exp(P, {"G": {"exercises": [T("f")]}})
out["W3a_helper_named__run"] = witlib.outcome(P, e, lambda cov: cov.run("G", _run, 1))
class Job:
    def _run(self): return m.f()     # a method named _run
e = witlib.exp(P, {"G": {"exercises": [T("f")]}})
out["W3b_method_named__run"] = witlib.outcome(P, e, lambda cov: cov.run("G", Job()._run))
# control: the real dispatch cut still works in both (a task step is not credited)
e = witlib.exp(P, {"G": {"exercises": [T("f")]}})
def h(cov):
    async def body():
        t = asyncio.get_running_loop().create_task(_acall())
        await t
    async def _acall(): m.f()
    cov.run("G", asyncio.run, body())
out["W3c_control_real_cut"] = witlib.outcome(P, e, h)
print(json.dumps(out))
