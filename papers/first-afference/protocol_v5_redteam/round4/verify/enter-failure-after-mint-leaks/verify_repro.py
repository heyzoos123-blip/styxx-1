# Independent verifier repro for "enter-failure-after-mint-leaks".
# Claim under test: an exception raised inside _CoverageTracer.__enter__ AFTER the mint loop has
# started (but before the state becomes "active") leaves minted __code__ installed, leaves the mint
# registered in _MINTED/_BY_FN with the dead tracer in m.tracers, so a later normal tracer (or an
# innocent enclosing tracer) never restores the original code; and the dead tracer (state still
# "new") can be re-entered, double-registering itself.
import json, os, signal, subprocess, sys, tempfile, textwrap, time
from pathlib import Path

sys.path.insert(0, os.environ.get("STYXX_ROOT", "/home/user/styxx-1"))
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace

TMP = Path(tempfile.mkdtemp(prefix="vfy_enter_"))
sys.path.insert(0, str(TMP))


def mod(name):
    (TMP / f"{name}.py").write_text("def f(x=0):\n    return x\n\ndef g(x=0):\n    return x\n")
    sys.modules.pop(name, None)
    return __import__(name)


def exp_for(*targets, section="G"):
    d = Path(tempfile.mkdtemp(prefix="vfy_repo_"))
    spec = {"gates": {section: {"metric": "m", "op": ">=", "value": 0.5,
                                "exercises": list(targets)}},
            "outcomes": [{"when": {section: True}, "verdict": "PASS"},
                         {"when": {}, "verdict": "FAIL"}], "smoke_verdict": "S"}
    p = d / "PREREG_v.md"
    p.write_text("# v\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=d, check=True)
    return Experiment(p)


def regs():
    return {"MINTED": len(P._MINTED), "BY_FN": len(P._BY_FN), "ACTIVE": P._ACTIVE,
            "STOP_set": P._STOP is not None}


def reset_registries(*fns_and_orig):
    for fn, orig in fns_and_orig:
        fn.__code__ = orig
    P._MINTED.clear(); P._BY_FN.clear(); P._ACTIVE = 0; P._STOP = None


out = {}

# ---- A: an audit hook (sandbox policy) refuses the __code__ write on the 2nd target ------------
mA = mod("vfy_a")
FA, GA = mA.f.__code__, mA.g.__code__
armed = [False]


def audit(ev, args):
    if armed[0] and ev == "object.__setattr__" and len(args) >= 2 and args[1] == "__code__" \
            and args[0] is mA.g:
        raise PermissionError("policy: no __code__ writes on g")


sys.addaudithook(audit)
expA = exp_for("vfy_a:f", "vfy_a:g")
trA = coverage_trace(expA)
armed[0] = True
try:
    with trA:
        pass
    out["A_enter"] = "entered"
except PermissionError as e:
    out["A_enter"] = f"PermissionError: {e}"
armed[0] = False
out["A_after_failed_enter"] = dict(f_minted=mA.f.__code__ is not FA, g_minted=mA.g.__code__ is not GA,
                                   tracer_state=trA._state, **regs())

# a later, fully legitimate tracer on f alone
exp2 = expA.__class__  # placeholder to keep names distinct
exp2 = exp_for("vfy_a:f")
with coverage_trace(exp2) as c2:
    c2.run("G", mA.f, 1)
try:
    v = exp2.score({"m": 1.0, "coverage_trace": c2.record()})
    out["A_later_trace_verdict"] = f"{v.verdict} {v.coverage}"
except GateSpecError as e:
    out["A_later_trace_verdict"] = f"REFUSED {str(e)[:120]}"
out["A_after_later_trace_exit"] = dict(f_restored=mA.f.__code__ is FA, **regs())

# retry of the same (still "new") tracer object after its failed enter
with trA:
    trA.run("G", lambda: (mA.f(1), mA.g(1)))
recA = trA.record()
out["A_retry_calls_for_one_call_each"] = recA["sections"]["G"][0]["calls"]
out["A_retry_problems"] = [p[:70] for p in recA["problems"]]
out["A_after_retry"] = dict(f_restored=mA.f.__code__ is FA, g_restored=mA.g.__code__ is GA, **regs())
reset_registries((mA.f, FA), (mA.g, GA))

# ---- B: an exception landing on the `self._state = "active"` line (after _ACTIVE += 1) -------------
# deterministic stand-in for an asynchronous exception (Ctrl-C / signal-handler exception)
mB = mod("vfy_b")
FB = mB.f.__code__
expB = exp_for("vfy_b:f")
enter_code = P._CoverageTracer.__enter__.__code__
import inspect
src, first = inspect.getsourcelines(P._CoverageTracer.__enter__)
line_active = first + next(i for i, l in enumerate(src) if 'self._state = "active"' in l)


def tr(frame, ev, arg):
    if frame.f_code is enter_code:
        def lt(fr, e, a):
            if e == "line" and fr.f_lineno == line_active:
                raise KeyboardInterrupt("async exc at _state='active'")
            return lt
        return lt
    return None


sys.settrace(tr)
try:
    with coverage_trace(expB):
        pass
except KeyboardInterrupt as e:
    out["B_enter"] = f"KeyboardInterrupt: {e}"
finally:
    sys.settrace(None)
out["B_after"] = dict(f_minted=mB.f.__code__ is not FB, **regs())
reset_registries((mB.f, FB))

# ---- C: a REAL asynchronous signal exception (SIGALRM via setitimer) hitting __enter__ ------------
class Alarm(BaseException):   # like pytest-timeout's Failed (BaseException)
    pass


def on_alarm(signum, frame):
    raise Alarm()


mC = mod("vfy_c")
FC, GC = mC.f.__code__, mC.g.__code__
expC = exp_for("vfy_c:f", "vfy_c:g")
signal.signal(signal.SIGALRM, on_alarm)
trials = leaks = enter_raises = 0
deadline = time.monotonic() + 25
example = None
while time.monotonic() < deadline and leaks < 5:
    trials += 1
    t = coverage_trace(expC)
    entered = False
    try:
        signal.setitimer(signal.ITIMER_REAL, 0.00002 + (trials % 97) * 0.000003)
        with t:
            entered = True
        signal.setitimer(signal.ITIMER_REAL, 0)
    except Alarm:
        pass
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    if not entered and t._state != "exited":
        # the exception came out of __enter__ (never out of the body or __exit__)
        enter_raises += 1
        holds = any(t in m.tracers for m in list(P._BY_FN.values()))
        if holds or mC.f.__code__ is not FC or mC.g.__code__ is not GC:
            leaks += 1
            if example is None:
                example = dict(trial=trials, tracer_state=t._state,
                               f_minted=mC.f.__code__ is not FC, g_minted=mC.g.__code__ is not GC,
                               **regs())
    if P._BY_FN or P._MINTED or P._ACTIVE or mC.f.__code__ is not FC or mC.g.__code__ is not GC:
        reset_registries((mC.f, FC), (mC.g, GC))
signal.signal(signal.SIGALRM, signal.SIG_DFL)
out["C_real_sigalrm"] = dict(trials=trials, exceptions_out_of_enter=enter_raises,
                             leaks_after_failed_enter=leaks, first_leak=example)

print(json.dumps(out, indent=1, default=str))
