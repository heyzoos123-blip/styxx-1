"""Verifier's own repro: a section argument that is a str subclass equal to the declared name."""
import enum, json, subprocess, sys, tempfile
from pathlib import Path
sys.path.insert(0, "/home/user/styxx-1")
from styxx.protocol import Experiment, GateSpecError, coverage_trace

d = Path(tempfile.mkdtemp(prefix="vss_"))
(d / "vss_mod.py").write_text("def f():\n    return 1\n")
sys.path.insert(0, str(d))
import vss_mod

spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["vss_mod:f"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "S"}
p = d / "PREREG_v.md"
p.write_text("# v\n\n```gates\n" + json.dumps(spec) + "\n```\n")
for c in (["git", "init", "-q"], ["git", "add", "-A"],
          ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false", "commit", "-qm", "c"]):
    subprocess.run(c, cwd=d, check=True)
exp = Experiment(p)

class S(str): pass
class E(str, enum.Enum):
    G = "G"          # name == value
    OTHER = "G2"
class E2(str, enum.Enum):
    GATE = "G"       # name != value: hash(E2.GATE) == hash("GATE") != hash("G")

def trial(label, *secs):
    with coverage_trace(exp) as cov:
        for s in secs:
            cov.run(s, vss_mod.f)
    rec = cov.record()
    keys = [(type(k).__name__, str.__str__(k)) for k in rec["sections"]]
    calls = {str.__str__(k): [o["calls"] for o in v] for k, v in rec["sections"].items()}
    try:
        out = f"PASS coverage={exp.score({'m': 1.0, 'coverage_trace': rec}).coverage}"
    except GateSpecError as e:
        out = f"REFUSED {str(e)[:80]}"
    cm = exp.check_metrics({"m": 1.0, "coverage_trace": rec})
    try:
        rt = exp.score({'m': 1.0, 'coverage_trace': json.loads(json.dumps(rec))})
        rtout = f"PASS {rt.coverage}"
    except GateSpecError as e:
        rtout = f"REFUSED {str(e)[:60]}"
    print(f"{label:34s} keys={keys} calls={calls}\n    score: {out}\n    json-roundtrip: {rtout}\n    check_metrics: {cm}")

print(sys.version.split()[0])
trial("control 'G'", "G")
trial("str subclass S('G')", S("G"))
trial("(str,Enum) E.G", E.G)
trial("(str,Enum) name!=value E2.GATE", E2.GATE)
trial("'G' then S('G')", "G", S("G"))
trial("S('G') then 'G'", S("G"), "G")
trial("'G' then E2.GATE", "G", E2.GATE)
# the open check itself: undeclared str subclass value is still refused UNDECLARED_SECTION
with coverage_trace(exp) as cov:
    try:
        cov.run(E.OTHER, vss_mod.f); print("E.OTHER accepted?!")
    except GateSpecError as e:
        print("E.OTHER at open:", str(e)[:50])
import styxx.protocol as P
print("leftovers:", sys.getprofile(), P._THREADS, P._ANCHORS, P._MINTED, P._BY_FN, P._ACTIVE)
