# usage: python witness.py <module file> <case>
import sys, os, json, subprocess, tempfile, textwrap, importlib.util, types, operator, asyncio
modfile, case = sys.argv[1], sys.argv[2]
W = tempfile.mkdtemp(prefix="rev9w_")
open(os.path.join(W, "fx9.py"), "w").write("def f(x=0): return x + 1\n")
sys.path.insert(0, W)
import fx9
spec = {"gates": {"A": {"metric": "m", "op": ">=", "value": 0.0, "exercises": ["fx9:f"]}},
        "outcomes": [{"when": {"A": True}, "verdict": "PASS"}, {"when": {"A": False}, "verdict": "FAIL"}],
        "smoke_verdict": "INVALID__smoke"}
open(os.path.join(W, "PREREG_W.md"), "w").write("# w\n\n```gates\n" + json.dumps(spec) + "\n```\n")
g = ["git", "-c", "user.name=w", "-c", "user.email=w@invalid", "-c", "commit.gpgsign=false"]
subprocess.run(["git", "init", "-q"], cwd=W, check=True)
subprocess.run(g + ["add", "."], cwd=W, check=True)
subprocess.run(g + ["commit", "-q", "-m", "w"], cwd=W, check=True)
sp = importlib.util.spec_from_file_location("styxx_protocol_w", modfile)
P = importlib.util.module_from_spec(sp); sys.modules["styxx_protocol_w"] = P; sp.loader.exec_module(P)
EXP = lambda: P.Experiment(os.path.join(W, "PREREG_W.md"))
def outcome(cov):
    try:
        rec = cov.record()
    except P.GateSpecError as e:
        return str(e)[:40]
    notes = [n[:18] for o in rec["sections"].get("A", []) for n in o["notes"]]
    try:
        v = EXP().score({"m": 1.0, "coverage_trace": rec})
        return ("PASS", v.coverage, notes)
    except P.GateSpecError as e:
        return ("REFUSE", str(e)[:22], "dispatched" in str(e) and str(e)[str(e).find("dispatched"):][:40], notes)
def ct():
    try:
        return P.coverage_trace(EXP())
    except P.GateSpecError as e:
        return str(e)[:26]
M = sys.monitoring
if case == "V69b":          # wrapper on get_local_events AFTER the first binding
    with P.coverage_trace(EXP()) as cov: cov.run("A", fx9.f)
    real = M.get_local_events; n = [0]
    def wrap(*a):
        n[0] += 1; return real(*a)
    M.get_local_events = wrap
    with P.coverage_trace(EXP()) as cov: cov.run("A", fx9.f)
    st = P._v5_state()
    M.get_local_events = real
    print(case, outcome(cov), "calls", n[0])
elif case == "V69c":        # the same with a wrapper that reports 0 (a lying read)
    with P.coverage_trace(EXP()) as cov: cov.run("A", fx9.f)
    real = M.get_local_events; n = [0]
    def wrap(*a):
        n[0] += 1; return 0
    M.get_local_events = wrap
    with P.coverage_trace(EXP()) as cov: cov.run("A", fx9.f)
    M.get_local_events = real
    print(case, outcome(cov), "calls", n[0])
elif case == "X156f":       # wrapper on get_local_events BEFORE the first binding
    real = M.get_local_events
    M.get_local_events = lambda *a: real(*a)
    r = ct()
    print(case, r if isinstance(r, str) else "constructed")
elif case in ("X156g", "X156g_ctl"):   # asyncio.events._get_running_loop replaced by a Python function
    import asyncio.events as ev
    class L(asyncio.SelectorEventLoop):          # X65d's shape: no Handle._run, no BaseEventLoop._run_once frame
        def _run_once(self):
            self._process_events(self._selector.select(0))
            hs = [self._ready.popleft() for _ in range(len(self._ready))]
            list(map(_go, hs))
    def _go(h):
        if not h._cancelled: h._callback(*h._args)
    async def main(): return fx9.f()
    if case == "X156g":
        ev._get_running_loop = lambda: None
    cov = ct()
    if isinstance(cov, str):
        print(case, cov); sys.exit()
    def body():
        lp = L()
        try: return lp.run_until_complete(main())
        finally: lp.close()
    with cov: cov.run("A", body)
    print(case, outcome(cov))
