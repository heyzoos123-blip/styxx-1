import json, os, subprocess, sys, tempfile
REF = "/home/user/styxx-1/papers/first-afference/v5f_exam/ref_v5f.py"
mode = sys.argv[1]
src = open(REF).read()
PATCH = {"p04": ("        if cur is None or id(cur) in seen:", "        if cur is None:"),
         "e03": ("    fns = [r for r in refs if type(r) is FunctionType and r is not m.fn]", "    fns = [r for r in refs if type(r) is FunctionType]"),
         "e06": ("        m.holders = tuple([h for h in m.holders if h is not core])\n        if not m.holders:\n            _retire(m)",
                 "        m.holders = tuple([h for h in m.holders if h is not core])\n        _retire(m)"),
         "s04": ("                union[t] = union.get(t, 0) + n", "                union[t] = n"),
         "s05": ("                union[t] = union.get(t, 0) + n", "                union[t] = max(union.get(t, 0), n)"),
         "s08": ('                    for t in missing if t in tr["uncredited"]["dispatched"]}', '                    for t in c["exercises"] if t in tr["uncredited"]["dispatched"]}'),
         "pl": ("    lost = r[-1] is not _TOOL_NAME", "    lost = r[-1] is None")}
if mode in PATCH:
    o, n = PATCH[mode]
    assert src.count(o) == 1, mode
    src = src.replace(o, n)
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "styxx")); open(os.path.join(d, "styxx", "__init__.py"), "w").write("")
open(os.path.join(d, "styxx", "protocol.py"), "w").write(src)
sys.path.insert(0, d)
import styxx.protocol as P
open(os.path.join(d, "fxo.py"), "w").write("def a(): return 1\ndef b(): return 2\na.__wrapped__ = b\nb.__wrapped__ = a\n")
open(os.path.join(d, "fxm.py"), "w").write("from fxo import a\ndef f(x=0): return x\ndef g(x=0): return x\n")
import fxm
def exp(gates):
    r = tempfile.mkdtemp()
    g = {n: {"metric": "m", "op": ">=", "value": 0.5, "exercises": t} for n, t in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {n: True for n in g}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = os.path.join(r, "PREREG_x.md"); open(p, "w").write("# x\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qm", "x"]):
        subprocess.run(c, cwd=r, check=True, capture_output=True)
    return P.Experiment(p)
def score(e, rec):
    try:
        v = e.score({"m": 1.0, "coverage_trace": rec}); return f"PASS {v.coverage}"
    except P.GateSpecError as ex:
        return str(ex)[:260]
out = {}
try:
    with P.coverage_trace(exp({"G": ["fxm:a"]})):
        pass
    out["p04"] = "entered"
except P.GateSpecError as ex:
    out["p04"] = str(ex)[:300]
# S04/S05: two openings each calling f once
e = exp({"G": ["fxm:f"]})
with P.coverage_trace(e) as cov:
    cov.run("G", fxm.f); cov.run("G", fxm.f)
out["s04"] = score(e, cov.record())
# S08: f only dispatched, g credited and also dispatched
import asyncio
e = exp({"G": ["fxm:f", "fxm:g"]})
def body():
    fxm.g()
    loop = asyncio.new_event_loop()
    loop.call_soon(fxm.f); loop.call_soon(fxm.g); loop.call_soon(loop.stop)
    loop.run_forever(); loop.close()
with P.coverage_trace(e) as cov:
    cov.run("G", body)
out["s08"] = score(e, cov.record())
print(mode, json.dumps(out, indent=0))
