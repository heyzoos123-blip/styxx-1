import json, os, subprocess, sys, tempfile
REF = "/home/user/styxx-1/papers/first-afference/v5f_exam/ref_v5f.py"
mode = sys.argv[1]
src = open(REF).read()
rows = {r["id"]: r for r in json.load(open("/home/user/styxx-1/papers/first-afference/v5f_exam/sm1_gap62_rows.json"))}
if mode != "ref":
    for a, b in rows[mode]["patches"]:
        assert src.count(a) == 1
        src = src.replace(a, b)
d = tempfile.mkdtemp()
os.makedirs(os.path.join(d, "styxx")); open(os.path.join(d, "styxx", "__init__.py"), "w").write("")
open(os.path.join(d, "styxx", "protocol.py"), "w").write(src)
sys.path.insert(0, d)
import styxx.protocol as P
open(os.path.join(d, "fxm.py"), "w").write("def f(x=0): return x\ndef g(x=0): return x\n")
import fxm
def exp(gates):
    r = tempfile.mkdtemp()
    g = {n: {"metric": "m", "op": ">=", "value": 0.5, "exercises": t} for n, t in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {n: True for n in g}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = os.path.join(r, "PREREG_x.md"); open(p, "w").write("# x\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "-c", "user.email=a@b", "-c", "user.name=a", "commit", "-qm", "x"]):
        subprocess.run(c, cwd=r, check=True, capture_output=True)
    return P.Experiment(p)
out = {}
e = exp({"G": ["fxm:f", "fxm:g"]})
with P.coverage_trace(e) as cov:
    st = P._v5_state()
    out["inside_mints"] = [(m["target"], m["local_events"]) for m in st["mints"]]
    codes = [fxm.f.__code__, fxm.g.__code__]
    t = st["tool"]
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(r)
        res = {"child_local_events": [sys.monitoring.get_local_events(t, c) for c in codes],
               "child_state_mints": P._v5_state()["mints"]}
        os.write(w, json.dumps(res).encode()); os._exit(0)
    os.close(w)
    data = b""
    while True:
        chunk = os.read(r, 65536)
        if not chunk: break
        data += chunk
    os.waitpid(pid, 0)
    out.update(json.loads(data))
print(mode, json.dumps(out))
