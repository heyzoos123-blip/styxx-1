"""Verifier's own repro: check_metrics on a smoke result vs a full result, same trace.

Cases:
  A  complete trace (f and g run)            -> expected usable True in both modes
  B  harness forgot g   (NOT_EXERCISED)      -> full: refusal text; smoke: ?
  C  section never opened (SECTION_ABSENT)   -> full: refusal text; smoke: ?
  D  stale trace (STALE_TRACE)               -> full: refusal text; smoke: ?
  E  no trace at all (NO_TRACE)              -> smoke masking is the v3 analog (absent)
Contrast on the same smoke result:
  v3 metric path present but a string  -> reports real reason on smoke
  composition 'over' present but a list -> reports real reason on smoke
"""
import copy, json, subprocess, sys, tempfile, uuid
from pathlib import Path
from styxx.protocol import Experiment, coverage_trace

tmp = Path(tempfile.mkdtemp(prefix="vf_smoke_"))
mod = "vf_mod_" + uuid.uuid4().hex[:8]
(tmp / f"{mod}.py").write_text("def f():\n    return 1\n\ndef g():\n    return 2\n")
sys.path.insert(0, str(tmp))
m = __import__(mod)
spec = {"gates": {
            "G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": [f"{mod}:f", f"{mod}:g"]},
            "S": {"metric": "s", "op": ">=", "value": 0.5},
            "C": {"metric": "c", "op": ">=", "value": 0.5, "agg": "max", "over": "pop"}},
        "outcomes": [{"when": {"G": True, "S": True, "C": True}, "verdict": "PASS"},
                     {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "SMOKE"}
repo = tmp / "repo"; repo.mkdir()
(repo / "PREREG_v.md").write_text("# v\n\n```gates\n" + json.dumps(spec) + "\n```\n")
for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
            ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
             "commit", "-qm", "x"]):
    subprocess.run(cmd, cwd=repo, check=True, capture_output=True)
exp = Experiment(repo / "PREREG_v.md")

def trace(body):
    with coverage_trace(exp) as cov:
        body(cov)
    return cov.record()

full_tr = trace(lambda cov: cov.run("G", lambda: (m.f(), m.g())))
forgot_g = trace(lambda cov: cov.run("G", m.f))
no_section = trace(lambda cov: None)
stale = copy.deepcopy(full_tr); stale["gates_sha256"] = "0" * 64

cases = {"A complete": full_tr, "B NOT_EXERCISED": forgot_g, "C SECTION_ABSENT": no_section,
         "D STALE_TRACE": stale, "E NO_TRACE": None}
print("python", sys.version.split()[0])
masked = []
for label, tr in cases.items():
    for smoke in (False, True):
        res = {"m": 1.0, "s": 1.0, "c": 1.0, "pop": {"a": 1.0}}
        if tr is not None:
            res["coverage_trace"] = tr
        if smoke:
            res["smoke"] = True
        e = exp.check_metrics(res)["G:exercises"]
        print(f"  {label:18s} smoke={smoke!s:5s} present={e['present']!s:5s} usable={e['usable']!s:5s} note={str(e['note'])[:70]!r}")
        if smoke and e["present"] and e["note"] == "smoke run":
            masked.append(label)
# what the other loops do on the same smoke result when the value is PRESENT but bad
res = {"m": 1.0, "s": "oops", "c": 1.0, "pop": [1.0], "smoke": True, "coverage_trace": forgot_g}
out = exp.check_metrics(res)
print("  contrast on smoke, value present but bad:")
print("    v3 S       :", out["S"]["usable"], repr(out["S"]["note"]))
print("    comp C:over:", out["C:over"]["usable"], repr(out["C:over"]["note"]))
print("    cov G      :", out["G:exercises"]["usable"], repr(out["G:exercises"]["note"]))
# score(smoke=True) never reads coverage
print("  score(smoke=True) with forgot_g ->", exp.score({"m": 1.0, "s": 1.0, "c": 1.0, "pop": {"a": 1.0}, "coverage_trace": forgot_g}, smoke=True).verdict)
print("MASKED-WITH-TRACE-PRESENT:", masked)
