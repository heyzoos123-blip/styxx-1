# Verifier's own deterministic repro (written from the claim, not from the reporter's script).
# An asynchronous exception (pytest-timeout style Timeout) is injected at the first line that
# runs AFTER `m.fn.__code__ = m.original` in _CoverageTracer.__exit__, i.e. between the restore
# and the unregistration. Then independent later traces of the same function are attempted.
import json, os, subprocess, sys, tempfile, textwrap
from pathlib import Path
sys.path.insert(0, os.environ.get("STYXX_ROOT", "/home/user/styxx-1"))
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace


class Timeout(Exception):
    pass


def mk_exp(target, gate="G"):
    d = Path(tempfile.mkdtemp(prefix="vdet_"))
    spec = {"gates": {gate: {"metric": "m", "op": ">=", "value": 0.5, "exercises": [target]}},
            "outcomes": [{"when": {gate: True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
            "smoke_verdict": "S"}
    p = d / "PREREG_x.md"
    p.write_text("# x\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=v@v", "-c", "user.name=v", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=d, check=True)
    return Experiment(p)


mdir = Path(tempfile.mkdtemp(prefix="vdet_mod_"))
(mdir / "vmod_target.py").write_text("def g(x):\n    return x + 1\n", encoding="utf-8")
sys.path.insert(0, str(mdir))
import vmod_target as tm
ORIG = tm.g.__code__

# locate the restore line and the line that follows it in __exit__ (by source, not by number)
import inspect
src, first = inspect.getsourcelines(P._CoverageTracer.__exit__)
k = next(i for i, l in enumerate(src) if "m.fn.__code__ = m.original" in l)
restore_line = first + k
EXIT_CODE = P._CoverageTracer.__exit__.__code__
seen_restore = {"v": False}


def tracer(frame, event, arg):
    if frame.f_code is not EXIT_CODE:
        return None

    def lt(fr, ev, a):
        if ev == "line":
            if fr.f_lineno == restore_line:
                seen_restore["v"] = True
            elif seen_restore["v"]:
                # first line event after the restore statement executed
                sys.settrace(None)
                fr.f_trace = None
                raise Timeout(f"timeout landed at line {fr.f_lineno} (restore is {restore_line})")
        return lt
    return lt


exp = mk_exp("vmod_target:g")
cov = coverage_trace(exp)
cov.__enter__()
cov.run("G", tm.g, 1)
sys.settrace(tracer)
try:
    cov.__exit__(None, None, None)
    print("exit completed (injection missed)")
except Timeout as e:
    print("exit interrupted:", e)
finally:
    sys.settrace(None)

try:
    cov.record()
except GateSpecError as e:
    print("record():", str(e)[:40])

m = P._BY_FN.get(id(tm.g))
print("state after interrupted exit: _ACTIVE=%d  _MINTED=%d  _BY_FN=%d  profile=%r"
      % (P._ACTIVE, len(P._MINTED), len(P._BY_FN), sys.getprofile()))
print("  g.__code__ is original:", tm.g.__code__ is ORIG,
      "| leftover mint tracers:", None if m is None else m.tracers,
      "| g.__code__ is mint code:", None if m is None else tm.g.__code__ is m.code)

# a fresh, independent trace of the same function (same experiment and a different one)
results = []
for label, e2 in (("same prereg", exp), ("other prereg", mk_exp("vmod_target:g", gate="H"))):
    sec = "G" if label == "same prereg" else "H"
    try:
        with coverage_trace(e2) as c2:
            c2.run(sec, tm.g, 2)
        v = e2.score({"m": 1.0, "coverage_trace": c2.record()})
        results.append((label, "PASS " + str(v.verdict)))
    except GateSpecError as err:
        results.append((label, "REFUSED " + str(err)))
for r in results:
    print("later trace (%s): %s" % r)

# with a different declared function in the same prereg too: only g's entry is poisoned
(mdir / "vmod_other.py").write_text("def h(x):\n    return x\n", encoding="utf-8")
import vmod_other
e3 = mk_exp("vmod_other:h")
with coverage_trace(e3) as c3:
    c3.run("G", vmod_other.h, 1)
print("unrelated target h:", e3.score({"m": 1.0, "coverage_trace": c3.record()}).verdict)

poisoned = all(r[1].startswith("REFUSED [V5:CODE_SWAPPED]") for r in results)
print("VERDICT:", "REPRODUCED" if poisoned else "NOT REPRODUCED")
