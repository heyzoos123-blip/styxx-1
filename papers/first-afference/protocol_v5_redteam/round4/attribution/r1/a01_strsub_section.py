"""A section name that is a str SUBCLASS (enum.StrEnum member, numpy.str_, a str-mixin Enum)
passes _open's `section in coverage_sections` check (str equality), is stored as the dict key in
record(), and then score()'s own exact-type schema check refuses the tracer's OWN trace as
BAD_TRACE ("sections must be a dict with str keys"). The target WAS executed in the section."""
import json, subprocess, sys, tempfile, enum
from pathlib import Path
sys.path.insert(0, "/home/user/styxx-1")
from styxx.protocol import Experiment, GateSpecError, coverage_trace

FIX = Path(tempfile.mkdtemp(prefix="a01fx_"))
(FIX / "a01_fix.py").write_text("def f(): return 1\n")
sys.path.insert(0, str(FIX))
import a01_fix

def mkexp(gates):
    td = Path(tempfile.mkdtemp(prefix="a01_"))
    g = {n: {"metric": "m", "op": ">=", "value": 0.5, **x} for n, x in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {n: True for n in g}, "verdict": "PASS"},
                                     {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = td / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=td, check=True)
    return Experiment(p)

class Sec(str, enum.Enum):            # the pre-3.11 spelling of StrEnum; works on 3.10-3.13
    G = "G"

class S(str):                         # any str subclass (numpy.str_ is one)
    pass

names = {"str-mixin Enum member": Sec.G, "plain str subclass": S("G")}
try:
    import numpy as np
    names["numpy.str_ (element of np.array(['G']))"] = np.array(["G"])[0]
except Exception:
    pass
if sys.version_info >= (3, 11):
    SE = enum.StrEnum("SE", {"G": "G"})
    names["enum.StrEnum member"] = SE.G

exp = mkexp({"G": {"exercises": ["a01_fix:f"]}})
results = {}
for label, sec in names.items():
    with coverage_trace(exp) as cov:
        cov.run(sec, a01_fix.f)                         # f IS executed on G's stack
    rec = cov.record()
    key = next(iter(rec["sections"]))
    calls = rec["sections"][key][0]["calls"]
    try:
        v = exp.score({"m": 1.0, "coverage_trace": rec})
        results[label] = f"PASS {v.coverage}"
    except GateSpecError as e:
        results[label] = f"REFUSED {str(e)[:110]}  (key type {type(key).__name__}, calls {calls})"
    # control: the same trace after a JSON round trip scores PASS
    rt = json.loads(json.dumps(rec))
    try:
        exp.score({"m": 1.0, "coverage_trace": rt})
        results[label] += " | json round-trip: PASS"
    except GateSpecError as e:
        results[label] += f" | json round-trip: {str(e)[:60]}"
with coverage_trace(exp) as cov:
    cov.run("G", a01_fix.f)
ctrl = exp.score({"m": 1.0, "coverage_trace": cov.record()}).verdict
for k, v in results.items():
    print(f"  {k}: {v}")
bad = [k for k, v in results.items() if v.startswith("REFUSED") and "BAD_TRACE" in v]
print(f"  control (plain 'G'): {ctrl}")
if bad and ctrl == "PASS":
    print(f"FINDING-REPRODUCED: a str-subclass section name ({', '.join(bad)}) is accepted at open, "
          f"f runs in the section, and score() refuses the tracer's own in-process trace BAD_TRACE")
else:
    print("no finding: str-subclass section names score as expected")
