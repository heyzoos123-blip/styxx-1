"""Independent repro for nested-and-lazy-texts-misstate.
(a) same-section self-nesting with ONE declaring gate -> NESTED_SECTION text says 'two gates'.
    Contrast: two distinct sections -> the same text (plausible there).
(b1) regular fn does all its target calls in the section and returns a genexpr -> LAZY_RESULT note
     'none of it counts' while f is credited to that opening.
(b1g) same, genexpr body calls g -> g really is uncredited (the note is true of the GENERATOR body).
(b2) fn advances a generator inside the section (generator body calls g, credited) then returns it
     -> note still says 'its body runs after the section closed, so none of it counts'.
"""
import json, subprocess, sys, tempfile, uuid
from pathlib import Path
from styxx.protocol import Experiment, GateSpecError, coverage_trace

tmp = Path(tempfile.mkdtemp(prefix="vf_nl_"))
mn = "vf_nl_" + uuid.uuid4().hex[:8]
(tmp / f"{mn}.py").write_text("def f():\n    return 1\n\ndef g():\n    return 2\n")
sys.path.insert(0, str(tmp))
mod = __import__(mn)

def mkexp(gates, tag):
    spec = {"gates": gates, "outcomes": [{"when": {}, "verdict": "FAIL"}], "smoke_verdict": "SMOKE"}
    repo = tmp / tag; repo.mkdir()
    (repo / "PREREG_x.md").write_text("# x\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false", "commit", "-qm", "x"]):
        subprocess.run(c, cwd=repo, check=True, capture_output=True)
    return Experiment(repo / "PREREG_x.md")

G1 = {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": [f"{mn}:f", f"{mn}:g"]}}
exp1 = mkexp(G1, "one")
print("python", sys.version.split()[0], "| gates declaring section G:",
      [n for n, c in exp1.coverage.items() if c["section"] == "G"])

# (a) self-nesting
with coverage_trace(exp1) as cov:
    def inner():
        try:
            cov.run("G", mod.g); return None
        except GateSpecError as e:
            return str(e)
    a = cov.run("G", inner)
print("(a) same section, 1 gate :", a)

# contrast: two distinct sections
G2 = {"A": {"metric": "m", "op": ">=", "value": 0.5, "exercises": [f"{mn}:f"]},
      "B": {"metric": "m", "op": ">=", "value": 0.5, "exercises": [f"{mn}:g"]}}
exp2 = mkexp(G2, "two")
with coverage_trace(exp2) as cov:
    def innerAB():
        try:
            cov.run("B", mod.g); return None
        except GateSpecError as e:
            return str(e)
    a2 = cov.run("A", innerAB)
print("(a') sections A>B, 2 gates:", a2)

def score_msg(exp, rec):
    try:
        exp.score({"m": 1.0, "coverage_trace": rec}); return "no refusal"
    except GateSpecError as e:
        return str(e)

# (b1) regular fn, genexpr over precomputed results
with coverage_trace(exp1) as cov:
    def b1():
        rs = [mod.f() for _ in range(3)]
        return (r * 2 for r in rs)
    list(cov.run("G", b1))
rec = cov.record(); op = rec["sections"]["G"][0]
print("(b1) calls", op["calls"], "notes", op["notes"])
print("     score:", score_msg(exp1, rec)[:400])

# (b1g) genexpr body calls g after close
with coverage_trace(exp1) as cov:
    def b1g():
        mod.f()
        return (mod.g() for _ in range(2))
    list(cov.run("G", b1g))
rec = cov.record(); op = rec["sections"]["G"][0]
print("(b1g) calls", op["calls"], "uncredited", rec["uncredited"], "notes", op["notes"])

# (b2) generator advanced inside the section, then returned
def genfn():
    mod.f(); yield 1
    mod.g(); yield 2
with coverage_trace(exp1) as cov:
    def b2():
        gen = genfn(); next(gen); next(gen)   # f and g run inside the section
        return gen
    list(cov.run("G", b2))
rec = cov.record(); op = rec["sections"]["G"][0]
print("(b2) calls", op["calls"], "notes", op["notes"])
print("     score:", score_msg(exp1, rec)[:200])
