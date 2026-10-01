import json, os, subprocess, sys, tempfile
exec(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "census_p04_s04_s05_s08.py")).read().split("import fxm")[0])
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
        return str(ex)[:160]
out = {}
# E03: nested; inner keeps a non-function reference to f's minted code past its exit
eo, ei = exp({"O": ["fxm:f"]}), exp({"I": ["fxm:f"]})
keep = []
with P.coverage_trace(eo) as o:
    with P.coverage_trace(ei) as i:
        i.run("I", lambda: (fxm.f(1), keep.append(fxm.f.__code__)) and None)
    out["e03_inner"] = score(ei, i.record())
    keep.clear()
    o.run("O", fxm.f, 2)
out["e03_outer"] = score(eo, o.record())
# E06: nested; inner exits first; outer calls f after
eo, ei = exp({"O": ["fxm:g"]}), exp({"I": ["fxm:g"]})
with P.coverage_trace(eo) as o:
    with P.coverage_trace(ei) as i:
        i.run("I", fxm.g, 1)
    o.run("O", fxm.g, 2)
out["e06_outer"] = score(eo, o.record())
out["e06_inner"] = score(ei, i.record())
# PL: the tool id taken by another name during the trace
mon = sys.monitoring
e = exp({"G": ["fxm:f"]})
with P.coverage_trace(e) as c:
    c.run("G", fxm.f, 1)
    t = P._v5_state()["tool"]
    mon.free_tool_id(t); mon.use_tool_id(t, "intruder")
rec = c.record()
out["pl"] = {"score": score(e, rec), "notes": [n[:40] for ops in rec["sections"].values() for o_ in ops for n in o_["notes"]], "problems": [p[:40] for p in rec["problems"]]}
try:
    mon.free_tool_id(t)
except Exception:
    pass
print(mode, json.dumps(out, indent=0))
