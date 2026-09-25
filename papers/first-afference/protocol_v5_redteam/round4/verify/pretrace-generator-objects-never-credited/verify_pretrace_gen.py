# Independent verifier repro: generator / coroutine objects created BEFORE coverage_trace entry,
# whose whole body then runs inside cov.run / cov.run_async on the anchor's own stack.
# Controls: the same objects created INSIDE the trace (outside and inside the section).
import asyncio, json, os, subprocess, sys, tempfile
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "mods"))
sys.path.insert(0, os.environ.get("STYXX_ROOT", "/home/user/styxx-1"))
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace
import vgen

def make_exp():
    d = Path(tempfile.mkdtemp(prefix="vpg_"))
    g = {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["vgen:stream"]},
         "H": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["vgen:fetch"]}}
    spec = {"gates": g, "outcomes": [{"when": {"G": True, "H": True}, "verdict": "PASS"},
                                     {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = d / "PREREG_v.md"
    p.write_text("# v\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=d, check=True)
    return Experiment(p)

def verdict(exp, rec):
    try:
        return "PASS " + exp.score({"m": 1.0, "coverage_trace": rec}).verdict
    except GateSpecError as e:
        return "REFUSED " + str(e)

def trial(label, when):
    exp = make_exp()
    orig = vgen.stream.__code__
    pre_g = pre_c = None
    if when == "pre":                                 # built at harness setup
        pre_g = vgen.stream(3); pre_c = vgen.fetch(10)
    body = []
    with coverage_trace(exp) as cov:
        if when == "in_trace":                        # built in the trace, outside any section
            pre_g = vgen.stream(3); pre_c = vgen.fetch(10)
        if when == "in_section":
            body.append(cov.run("G", lambda: list(vgen.stream(3))))
            async def drive(): return await vgen.fetch(10)
        else:
            g, c = pre_g, pre_c
            body.append(cov.run("G", lambda: list(g)))
            async def drive(): return await c
        body.append(asyncio.run(cov.run_async("H", drive)))
    rec = cov.record()
    assert vgen.stream.__code__ is orig
    print(f"--- {label} ({sys.version.split()[0]})")
    print("  body results:", body)
    print("  sections:", {k: [o["calls"] for o in v] for k, v in rec["sections"].items()},
          "notes:", [o["notes"] for v in rec["sections"].values() for o in v])
    print("  uncredited:", rec["uncredited"], "problems:", rec["problems"])
    print("  score:", verdict(exp, rec)[:260])
    return rec

a = trial("A: objects created BEFORE trace", "pre")
b = trial("B: control, created in trace outside sections", "in_trace")
c = trial("C: control, created inside the sections", "in_section")
lost = all(o["calls"] == {} for v in a["sections"].values() for o in v)
ctrl = all(o["calls"] for r in (b, c) for v in r["sections"].values() for o in v)
print("RESULT:", "pre-trace objects lost, controls credited" if lost and ctrl else "no divergence")
