# ---- self-contained prelude (identical in every script of this lens) ----
import json, os, subprocess, sys, tempfile, textwrap, threading, types
from pathlib import Path
sys.path.insert(0, os.environ.get("STYXX_ROOT", "/home/user/styxx-1"))
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace

_TMP = Path(tempfile.mkdtemp(prefix="rt4id_"))
sys.path.insert(0, str(_TMP))

def write_mod(name, src):
    (_TMP / f"{name}.py").write_text(textwrap.dedent(src), encoding="utf-8")
    sys.modules.pop(name, None)

def make_exp(**gates):
    d = Path(tempfile.mkdtemp(prefix="rt4id_repo_"))
    g = {k: {"metric": "m", "op": ">=", "value": 0.5, **v} for k, v in gates.items()}
    spec = {"gates": g, "outcomes": [{"when": {k: True for k in g}, "verdict": "PASS"},
                                     {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = d / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=d, check=True)
    return Experiment(p)

def score(exp, rec, m=1.0):
    try:
        v = exp.score({"m": m, "coverage_trace": rec})
        return f"PASS verdict={v.verdict} coverage={v.coverage}"
    except GateSpecError as e:
        return f"REFUSED {str(e)[:220]}"

def leftovers():
    return dict(profile=sys.getprofile(), minted=len(P._MINTED), by_fn=len(P._BY_FN),
                anchors=len(P._ANCHORS), threads=len(P._THREADS), active=P._ACTIVE)
# ---- end prelude ----
# ATTACK 08: an exit interrupted between the restore (`m.fn.__code__ = m.original`) and the
# unregistration (`_MINTED.pop` / `_BY_FN.pop`) leaves a registered mint whose code is no longer
# installed. The spec calls an interrupted exit "equal code and harmless" (TRACE_INCOMPLETE for
# that trace only). In fact EVERY later tracer that declares the function is refused at entry with
# CODE_SWAPPED ("an enclosing trace minted it and its __code__ has since been replaced") -- no
# enclosing trace exists and nothing was swapped -- for the rest of the process.
# The interruption is an asynchronous KeyboardInterrupt (Ctrl-C / a signal-based timeout),
# simulated deterministically with a line tracer at the unregistration line.
import inspect
write_mod("rt4_exit", """
    def f(x=0): return x
""")
import rt4_exit as me
exp = make_exp(G={"exercises": ["rt4_exit:f"]})
exit_code = P._CoverageTracer.__exit__.__code__
lines, first = inspect.getsourcelines(P._CoverageTracer.__exit__)
pop_line = first + next(k for k, l in enumerate(lines) if "_MINTED.pop(id(m.code)" in l)

def _tr(frame, ev, arg):
    if frame.f_code is exit_code:
        def _lt(fr, e, a):
            if e == "line" and fr.f_lineno == pop_line:
                raise KeyboardInterrupt("simulated Ctrl-C inside __exit__")
            return _lt
        return _lt
    return None

tr = coverage_trace(exp)
try:
    with tr:
        tr.run("G", me.f, 1)
        sys.settrace(_tr)
except KeyboardInterrupt as e:
    sys.settrace(None)
    print("first trace: exit interrupted:", e)
sys.settrace(None)
try:
    tr.record()
except GateSpecError as e:
    print("first trace record():", str(e)[:60])
print("state:", leftovers(), "| f restored:", me.f.__code__ is P._BY_FN and False or
      (list(P._BY_FN.values())[0].original is me.f.__code__ if P._BY_FN else None))

outs = []
for i in range(2):                       # later, independent, perfectly normal traces
    try:
        with coverage_trace(exp) as cov:
            cov.run("G", me.f, 1)
        outs.append(score(exp, cov.record()))
    except GateSpecError as e:
        outs.append("ENTER REFUSED " + str(e)[:170])
for o in outs:
    print("later trace:", o)
if all(o.startswith("ENTER REFUSED [V5:CODE_SWAPPED]") for o in outs):
    print("FINDING-REPRODUCED: after one interrupted exit, every later trace of the target is "
          "refused CODE_SWAPPED at entry although nothing swapped __code__ and no trace encloses it")
else:
    print("no finding:", outs)
