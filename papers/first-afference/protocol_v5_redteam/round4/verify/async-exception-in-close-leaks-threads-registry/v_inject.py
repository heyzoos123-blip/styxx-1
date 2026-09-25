"""Independent verifier repro (deterministic).

A real SIGALRM handler that raises Timeout is fired (signal.raise_signal) at one chosen source line of
_CoverageTracer._close or ._open, using a sys.settrace line tracer on that one frame only. That is
what an asynchronous exception at an eval-breaker on that line does. settrace tools are 'unaffected'
per the spec, and the hook is a setprofile hook, so the injection does not touch the hook.

Per window, it reports: where the Timeout surfaced, _THREADS/_ANCHORS/_ACTIVE after a completed exit,
the record's section entry, and whether a later clean tracer still has sys.getprofile() is _hook
right after its only section closed, and _THREADS after its exit.

usage: python v_inject.py <window>, where window is one of
  close_after_frame_none   (the line `st = _THREADS.get(o.tid)` in _close)
  close_before_decrement   (the line `if st is not None:` in _close, just before `st[0] -= 1`)
  close_before_pop         (the line `_ANCHORS.pop(id(o.frame), None)` in _close)
  open_opening_ctor        (the line `o = _Opening(self, section, anchor, tid, st[1])` in _open)
  open_after_append        (the line `_ANCHORS[id(anchor)] = o` in _open: the disclosed L-ASYNC-EXC side)
  none                     (control: no injection)
"""
import inspect, json, os, signal, subprocess, sys, tempfile
from pathlib import Path

ROOT = os.environ.get("STYXX_ROOT", "/home/user/styxx-1")
sys.path.insert(0, ROOT)
import styxx.protocol as P
from styxx.protocol import Experiment, coverage_trace

WINDOWS = {
    "close_after_frame_none": ("_close", "st = _THREADS.get(o.tid)"),
    "close_before_decrement": ("_close", "if st is not None:"),
    "close_before_pop": ("_close", "_ANCHORS.pop(id(o.frame), None)"),
    "open_opening_ctor": ("_open", "o = _Opening(self, section, anchor, tid, st[1])"),
    "open_after_append": ("_open", "_ANCHORS[id(anchor)] = o"),
}
window = sys.argv[1]

FIX = Path(tempfile.mkdtemp(prefix="vinj_fx_"))
(FIX / "vinj_fix.py").write_text("def f():\n    return 1\n")
sys.path.insert(0, str(FIX))
import vinj_fix


def mkexp():
    td = Path(tempfile.mkdtemp(prefix="vinj_"))
    spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": ["vinj_fix:f"]}},
            "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
            "smoke_verdict": "S"}
    p = td / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=td, check=True, capture_output=True)
    return Experiment(p)


class Timeout(Exception):
    pass


def handler(signum, frame):
    raise Timeout(f"SIGALRM handler raised in {frame.f_code.co_name}:{frame.f_lineno}")


signal.signal(signal.SIGALRM, handler)

target_code = target_line = None
if window != "none":
    meth, text = WINDOWS[window]
    fn = getattr(P._CoverageTracer, meth)
    target_code = fn.__code__
    src, first = inspect.getsourcelines(fn)
    hits = [first + i for i, l in enumerate(src) if l.strip().split("#")[0].strip() == text]
    assert len(hits) == 1, (window, hits)
    target_line = hits[0]

fired = []


def local(frame, event, arg):
    if event == "line" and frame.f_lineno == target_line and not fired:
        fired.append(target_line)
        signal.raise_signal(signal.SIGALRM)        # handler runs here and raises Timeout
    return local


def global_tracer(frame, event, arg):
    if frame.f_code is target_code and not fired:
        return local
    return None


exp = mkexp()
print(f"python {sys.version.split()[0]}  window={window}  line={target_line}")
surfaced = None
with coverage_trace(exp) as cov:
    cov.run("G", vinj_fix.f)                       # one clean section first
    if target_code is not None:
        sys.settrace(global_tracer)
    try:
        cov.run("G", vinj_fix.f)                   # the section the signal lands in
    except Timeout as e:
        surfaced = str(e)
    finally:
        sys.settrace(None)
    cov.run("G", vinj_fix.f)                       # one clean section after
    in_trace_after_close = sys.getprofile()
rec = cov.record()
print(f"  injected at line {fired}; Timeout surfaced: {surfaced!r}")
print(f"  hook on this thread after the last section closed (tracer still active): "
      f"{getattr(in_trace_after_close, '__name__', in_trace_after_close)}")
print(f"  record sections: {rec['sections']['G']}")
print(f"  after tracer 1 exit: _THREADS={P._THREADS} _ANCHORS={len(P._ANCHORS)} _ACTIVE={P._ACTIVE} "
      f"_MINTED={len(P._MINTED)} _BY_FN={len(P._BY_FN)} getprofile={sys.getprofile()}")
leak1 = dict(P._THREADS)

# phase 2: a brand-new tracer, no signals, no settrace
exp2 = mkexp()
with coverage_trace(exp2) as cov2:
    cov2.run("G", vinj_fix.f)
    after_close = sys.getprofile()
rec2 = cov2.record()
print(f"  tracer 2: getprofile() right after its only section closed = "
      f"{getattr(after_close, '__name__', after_close)}")
print(f"  tracer 2: section record {rec2['sections']['G']}")
print(f"  tracer 2: _THREADS after exit = {P._THREADS}")
res = {"m": 1.0, "coverage_trace": rec2}
try:
    print(f"  tracer 2 score: {exp2.score(res).verdict}")
except Exception as e:  # noqa
    print(f"  tracer 2 score raised: {type(e).__name__}: {str(e)[:160]}")
print("LEAK" if (leak1 or P._THREADS or after_close is not None) else "CLEAN")
