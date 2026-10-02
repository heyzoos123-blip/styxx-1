"""atfork_restores_first: what C9's fork scenario sees, and what a read before the child's first transaction sees.
usage: python probe.py ref|mut
A trace on fx.f with section A open and a pending entry forks; in the child an audit hook refuses the first
__code__ write (the sweep's audit variant, point ["write", 1]). The child reads _v5_state() and the fixtures' code
(a) right after the fork, before any transaction, and (b) after a probe cycle (a fresh tracer entered and exited);
the parent reads its record. Fresh process; no thread started before the fork."""
import json, os, subprocess, sys, tempfile
REF = "/home/user/styxx-1/papers/first-afference/v5f_exam/ref_v5f.py"
mode = sys.argv[1]
src = open(REF).read()
if mode == "mut":
    old = '    _GUARD["hint"] = _Txn(None, 0, None)             # 1.'
    new = ('    for m in list(_MINTED.values()):                 # mutant: restores moved first\n'
           '        if m.fn.__code__ is m.code:\n            m.fn.__code__ = m.original\n'
           '    _GUARD["hint"] = _Txn(None, 0, None)             # 1.')
    assert src.count(old) == 1
    src = src.replace(old, new)
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "styxx")); open(os.path.join(d, "styxx", "__init__.py"), "w").write("")
open(os.path.join(d, "styxx", "protocol.py"), "w").write(src)
open(os.path.join(d, "fxm.py"), "w").write("def f(x=0): return x\ndef g(x=0): return 2\n")
sys.path.insert(0, d)
import styxx.protocol as P
import fxm
ORIG = {"f": fxm.f.__code__, "g": fxm.g.__code__}
def exp(gates):
    r = tempfile.mkdtemp()
    g = {n: {"metric": "m", "op": ">=", "value": 0.5, "exercises": t} for n, t in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {n: True for n in g}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = os.path.join(r, "PREREG_x.md"); open(p, "w").write("# x\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qm", "x"]):
        subprocess.run(c, cwd=r, check=True, capture_output=True)
    return P.Experiment(p)
def state():
    st = P._v5_state()
    t = st["tool"]
    fix = {}
    for k, c in ORIG.items():
        fn = getattr(fxm, k)
        le = sys.monitoring.get_local_events(t, fn.__code__) if (t is not None and sys.monitoring.get_tool(t)) else None
        fix[k] = {"is_original": fn.__code__ is c, "equal": fn.__code__ == c, "local_events": le}
    return {"anchors": st["anchors"], "mints": st["mints"], "global_events": st["global_events"], "guard": st["guard"], "fixtures": fix}
e = exp({"A": ["fxm:f"]})
e2 = exp({"B": ["fxm:g"]})
parent = os.getpid()
writes = {"n": 0}
def hook(ev, args):
    if os.getpid() != parent and ev == "object.__setattr__" and len(args) > 1 and args[1] == "__code__":
        writes["n"] += 1
        if writes["n"] == 1:
            raise RuntimeError("the audit hook refuses the first __code__ write")
sys.addaudithook(hook)
r, w = os.pipe()
def body():
    fxm.f(1)                                   # a pending entry? (it returns before the fork: credited) -- keep a call
    pid = os.fork()
    if pid == 0:
        res = {"writes_refused_at": writes["n"], "before_any_transaction": state()}
        try:
            res["run_passthrough"] = cov.run("A", fxm.g)
        except BaseException as ex:            # noqa: BLE001
            res["run_passthrough"] = f"raised {type(ex).__name__}"
        res["after_passthrough"] = state()
        try:
            with P.coverage_trace(e2) as c2:
                c2.run("B", fxm.g)
            res["probe_cycle"] = "ok"
        except BaseException as ex:            # noqa: BLE001
            res["probe_cycle"] = f"raised {type(ex).__name__}: {str(ex)[:80]}"
        res["after_probe_cycle"] = state()
        os.write(w, json.dumps(res).encode()); os._exit(0)
    os.close(w)
    data = b""
    while True:
        chunk = os.read(r, 65536)
        if not chunk: break
        data += chunk
    os.waitpid(pid, 0)
    return json.loads(data)
with P.coverage_trace(e) as cov:
    child = cov.run("A", body)
rec = cov.record()
print(json.dumps({"mode": mode, "python": sys.version.split()[0], "child": child,
                  "parent_sections": {s: [o["calls"] for o in ops] for s, ops in rec["sections"].items()}, "parent_problems": rec["problems"],
                  "parent_state": state()}, indent=1))
