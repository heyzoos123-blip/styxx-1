"""A signal-handler exception (pytest-timeout's signal method, a SIGALRM Timeout, Ctrl-C) that
lands inside _close after `o.frame = None` and before `st[0] -= 1` -- or inside _open's
_Opening(...) call after `st[0] += 1` -- leaves _THREADS[tid] with a count that no opening owns.
__exit__ only decrements for openings whose frame is still set, so the entry is never removed:
it survives the tracer's exit and leaks into every later tracer, where that thread's last close
no longer removes the hook (sys.getprofile() stays _hook after every section closes).
The spec: "_close ... never raises"; L-ASYNC-EXC names only the gap between _open's
registration and run's try, whose worst case is an OPEN_AT_EXIT opening.

Phase 1 is real: a repeating SIGALRM whose handler raises Timeout while a harness runs many
short sections, retrying each trace until the leak appears (bounded). Phase 2 shows the
consequence in a fresh, clean tracer."""
import json, signal, subprocess, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, "/home/user/styxx-1")
import styxx.protocol as P
from styxx.protocol import Experiment, GateSpecError, coverage_trace

FIX = Path(tempfile.mkdtemp(prefix="a04fx_"))
(FIX / "a04_fix.py").write_text("def f(): return 1\n")
sys.path.insert(0, str(FIX))
import a04_fix

def mkexp(gates):
    td = Path(tempfile.mkdtemp(prefix="a04_"))
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

class Timeout(Exception):
    pass

def handler(signum, frame):
    raise Timeout()

exp = mkexp({"G": {"exercises": ["a04_fix:f"]}})
signal.signal(signal.SIGALRM, handler)
deadline = time.time() + 35
leaked, traces, timeouts = None, 0, 0
while time.time() < deadline and leaked is None:
    traces += 1
    try:
        with coverage_trace(exp) as cov:
            signal.setitimer(signal.ITIMER_REAL, 0.0003, 0.0003)
            try:
                for i in range(3000):
                    try:
                        cov.run("G", a04_fix.f)          # a batch of short per-case sections
                    except Timeout:
                        timeouts += 1                   # the harness's per-case timeout: skip it
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
    except Timeout:
        timeouts += 1
        signal.setitimer(signal.ITIMER_REAL, 0)
    if cov._state != "exited":
        # a Timeout landed in __exit__ itself (disclosed: TRACE_INCOMPLETE); tidy and retry
        P._ACTIVE = 0; P._ANCHORS.clear(); P._THREADS.clear(); P._MINTED.clear(); P._BY_FN.clear()
        a04_fix.f.__code__ = a04_fix.f.__code__.replace()
        sys.setprofile(None)
        continue
    if P._THREADS:
        leaked = dict(P._THREADS)
signal.setitimer(signal.ITIMER_REAL, 0)
signal.signal(signal.SIGALRM, signal.SIG_DFL)
print(f"  traces {traces}, Timeouts caught {timeouts}")
if leaked is None:
    print("no finding: no _THREADS leak observed within the time budget (timing-dependent)")
    sys.exit(0)
print(f"  after a completed exit: _THREADS = {leaked}, _ACTIVE = {P._ACTIVE}, "
      f"_ANCHORS = {len(P._ANCHORS)}")

# phase 2: a fresh tracer, no signals at all
with coverage_trace(exp) as cov2:
    cov2.run("G", a04_fix.f)
    after_close = sys.getprofile()                      # last (only) close on this thread done
rec2 = cov2.record()
after_exit = dict(P._THREADS)
print(f"  fresh tracer: sys.getprofile() after its section closed = {after_close!r}")
print(f"  fresh tracer: _THREADS after its exit = {after_exit}")
if after_close is not None or after_exit:
    print("FINDING-REPRODUCED: a signal-handler exception inside _close/_open leaks a _THREADS "
          "count past tracer exit into later tracers (hook no longer removed at last close)")
else:
    print("no finding: the leaked entry did not affect a later tracer")
