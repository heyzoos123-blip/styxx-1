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
# ATTACK 04: __enter__ fails AFTER minting (between the mint loop and `self._state = "active"`).
# Nothing restores the minted __code__: __exit__ is not called for a failed __enter__, the dead
# tracer stays in m.tracers, and so every LATER, perfectly normal tracer also exits without
# restoring (it is never "the last tracer holding the mint"). Registries never empty again.
# Three routes to the failure:
#   (i)  asyncio.events.Handle._run patched with a MagicMock (no __code__) -> AttributeError
#   (ii) an audit hook refusing the 2nd object.__setattr__('__code__') -> mid-loop failure
#   (iii) an asynchronous KeyboardInterrupt landing in the window (simulated deterministically)
import asyncio.events
from unittest import mock
write_mod("rt4_enter", """
    def f(x=0): return x
    def g(x=0): return x
""")
import rt4_enter as m4
F_ORIG, G_ORIG = m4.f.__code__, m4.g.__code__
exp = make_exp(G={"exercises": ["rt4_enter:f", "rt4_enter:g"]})
results = {}

# route (i)
with mock.patch.object(asyncio.events.Handle, "_run"):
    tr1 = coverage_trace(exp)
    try:
        with tr1:
            pass
        results["i"] = "entered?!"
    except AttributeError as e:
        results["i"] = f"AttributeError({e})"
after_i = dict(f_minted=m4.f.__code__ is not F_ORIG, g_minted=m4.g.__code__ is not G_ORIG,
               **leftovers())
print("(i) enter raised:", results["i"], "-> state after:", after_i)

# a later, completely normal tracer: counts fine, but does NOT restore the code
exp2 = make_exp(G={"exercises": ["rt4_enter:f"]})
with coverage_trace(exp2) as cov2:
    cov2.run("G", m4.f, 1)
print("   later normal trace:", score(exp2, cov2.record()))
after_later = dict(f_restored=m4.f.__code__ is F_ORIG, **leftovers())
print("   after the later normal trace exited:", after_later)

# retrying the SAME tracer object after the failed enter: state is still 'new', so it re-enters;
# it appends itself to m.tracers a second time and duplicates its names -> over-counting
with tr1:                                      # the tracer object from route (i)
    tr1.run("G", lambda: (m4.f(1), m4.g(1)))
rec = tr1.record()
print("   retry of the same tracer, one call each of f and g ->", rec["sections"]["G"][0]["calls"],
      "| problems:", [p[:60] for p in rec["problems"]])
print("   retry scored:", score(exp, rec)[:120])
retry_over = rec["sections"]["G"][0]["calls"].get("rt4_enter:f", 0) > 1

# route (ii): audit hook refusing the second __code__ assignment during the mint loop
write_mod("rt4_enter2", """
    def f(x=0): return x
    def g(x=0): return x
""")
import rt4_enter2 as m5
F5 = m5.f.__code__
_armed = [False]
def _audit(ev, args):
    if _armed[0] and ev == "object.__setattr__" and len(args) >= 2 and args[1] == "__code__" \
            and args[0] in (m5.g, globals().get("_target_g")):
        raise PermissionError("sandbox audit hook: __code__ writes on this function are not allowed")
sys.addaudithook(_audit)
exp5 = make_exp(G={"exercises": ["rt4_enter2:f", "rt4_enter2:g"]})
_armed[0] = True
try:
    with coverage_trace(exp5):
        pass
except PermissionError as e:
    print("(ii) enter raised:", e)
_armed[0] = False
print("   f left minted:", m5.f.__code__ is not F5, leftovers())

# route (ii'): an INNOCENT outer tracer is active on f; an inner tracer (another experiment,
# declaring f and g) fails half-way on g. The outer tracer then exits normally -- and does NOT
# restore f, because the dead inner tracer is still listed in f's mint.
write_mod("rt4_enter2b", """
    def f(x=0): return x
    def g(x=0): return x
""")
import rt4_enter2b as m5b
F5b = m5b.f.__code__
exp_outer = make_exp(O={"exercises": ["rt4_enter2b:f"]})
exp_inner = make_exp(I={"exercises": ["rt4_enter2b:f", "rt4_enter2b:g"]})
with coverage_trace(exp_outer) as outer:
    outer.run("O", m5b.f, 1)
    _armed[0] = True
    _target_g = m5b.g
    try:
        with coverage_trace(exp_inner):
            pass
    except PermissionError as e:
        print("(ii') inner enter raised:", e)
    _armed[0] = False
print("   outer (innocent) trace:", score(exp_outer, outer.record()))
print("   after the outer trace exited: f restored:", m5b.f.__code__ is F5b)

# route (iii): simulate an asynchronous KeyboardInterrupt at the `_STOP = ...` line of __enter__
write_mod("rt4_enter3", """
    def f(x=0): return x
""")
import rt4_enter3 as m6
F6 = m6.f.__code__
exp6 = make_exp(G={"exercises": ["rt4_enter3:f"]})
enter_code = P._CoverageTracer.__enter__.__code__
import dis
src_lines, first = __import__("inspect").getsourcelines(P._CoverageTracer.__enter__)
stop_line = first + next(k for k, l in enumerate(src_lines) if "_STOP = asyncio.events" in l)
def _tr(frame, ev, arg):
    if frame.f_code is enter_code:
        def _lt(fr, e, a):
            if e == "line" and fr.f_lineno == stop_line:
                raise KeyboardInterrupt("simulated Ctrl-C inside __enter__")
            return _lt
        return _lt
    return None
sys.settrace(_tr)
try:
    with coverage_trace(exp6):
        pass
except KeyboardInterrupt as e:
    sys.settrace(None)
    print("(iii) enter raised:", e)
sys.settrace(None)
print("   f left minted:", m6.f.__code__ is not F6, leftovers())

leak = after_i["f_minted"] and not after_later["f_restored"] and after_later["minted"] > 0
if leak:
    print("FINDING-REPRODUCED: an __enter__ that fails after minting leaves __code__ minted and "
          "registries populated; later normal tracers never restore it"
          + ("; retrying the same tracer over-counts" if retry_over else ""))
else:
    print("no finding: state restored")
