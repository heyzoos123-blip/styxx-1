import asyncio, importlib.util, json, os, subprocess, sys, tempfile, types
REF = "/home/user/styxx-1/papers/first-afference/v5f_exam/ref_v5f.py"
mode = sys.argv[1]
src = open(REF).read()
if mode == "h18":
    old = "    if f.f_globals is not m.globals:                # CLONE_CALLED: credits nothing"
    assert src.count(old) == 1
    src = src.replace(old, "    if f.f_globals != m.globals:                    # CLONE_CALLED: credits nothing")
if mode == "h15":
    old = "    found = []\n    cut = False\n    g = f.f_back"
    assert src.count(old) == 1
    src = src.replace(old, "    found = []\n    cut = False\n    g = f")
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "styxx"))
open(os.path.join(d, "styxx", "__init__.py"), "w").write("")
open(os.path.join(d, "styxx", "protocol.py"), "w").write(src)
sys.path.insert(0, d)
import styxx.protocol as P
fx = os.path.join(d, "fxm.py"); open(fx, "w").write("def f(): return 1\n"); 
import fxm
def exp(gates):
    r = tempfile.mkdtemp()
    g = {n: {"metric": "m", "op": ">=", "value": 0.5, "exercises": t} for n, t in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {n: True for n in g}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = os.path.join(r, "PREREG_x.md"); open(p, "w").write("# x\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qm", "x"]):
        subprocess.run(c, cwd=r, check=True, capture_output=True)
    return P.Experiment(p)
e = exp({"G": ["styxx.protocol:_run_async", "fxm:f"]}) if "h18" not in sys.argv[2:] else exp({"G": ["fxm:f"]})
async def body():
    fxm.f()
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    fxm.f()
def clone_call():
    g = dict(fxm.f.__globals__)
    return types.FunctionType(fxm.f.__code__, g)()
try:
    with P.coverage_trace(e) as cov:
        if "h18" in sys.argv[2:]:
            cov.run("G", clone_call)
        else:
            asyncio.run(cov.run_async("G", body))
    rec = cov.record()
    print(mode, json.dumps(rec["sections"]), json.dumps(rec["uncredited"]))
    try:
        print(mode, e.score({"m": 1.0, "coverage_trace": rec}).verdict)
    except P.GateSpecError as ex:
        print(mode, str(ex)[:150])
except P.GateSpecError as ex:
    print(mode, "ENTER", str(ex)[:200])
