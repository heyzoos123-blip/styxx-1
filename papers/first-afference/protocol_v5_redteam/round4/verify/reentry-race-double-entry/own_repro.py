"""Independent repro: concurrent __enter__ of ONE tracer object from two threads.

Scenarios (one per process, pass the letter as argv[1]):
  A  control: second __enter__ after the first completed -> REENTRY (spec behaviour)
  B  race: declared module imported for the first time; import does I/O (sleep) -> both enter
  C  race: module already imported (no I/O in resolution), default switch interval; N attempts
  D  race while a SEPARATE outer tracer (legit nested use, V15 shape) holds the same mints:
     module resolution is a PEP 562 lazy __getattr__ that does I/O -> both enter, no problem at all
  E  thread 2 passes the state check, is descheduled in resolution until thread 1 has fully
     exited; then its entry re-activates an EXITED tracer
"""
import importlib
import json
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
from pathlib import Path

from styxx.protocol import Experiment, GateSpecError, coverage_trace
import styxx.protocol as P

MODDIR = Path(tempfile.mkdtemp(prefix="rt4v_mod_"))
sys.path.insert(0, str(MODDIR))


def make_exp(targets, section="G"):
    td = Path(tempfile.mkdtemp(prefix="rt4v_exp_"))
    spec = {"gates": {section: {"metric": "m", "op": ">=", "value": 0.5, "exercises": targets}},
            "outcomes": [{"when": {section: True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
            "smoke_verdict": "S"}
    p = td / "PREREG_case.md"
    p.write_text("# case\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for c in (["git", "init", "-q"], ["git", "add", "-A"],
              ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
               "commit", "-qm", "c"]):
        subprocess.run(c, cwd=td, check=True)
    return Experiment(p)


def write_mod(name, src):
    (MODDIR / (name + ".py")).write_text(textwrap.dedent(src), encoding="utf-8")
    importlib.invalidate_caches()


def state():
    return dict(ACTIVE=P._ACTIVE, MINTED=len(P._MINTED), BY_FN=len(P._BY_FN),
                THREADS=len(P._THREADS), ANCHORS=len(P._ANCHORS), prof=sys.getprofile())


def race(cov, body, hold_inside=True):
    """Two workers each do `with cov: cov.run('G', body)`; both stay inside until both are in."""
    start = threading.Barrier(2)
    inside = threading.Barrier(2, timeout=3)
    out = {}

    def worker(i):
        start.wait()
        try:
            with cov:
                cov.run("G", body)
                if hold_inside:
                    try:
                        inside.wait()
                    except threading.BrokenBarrierError:
                        pass
            out[i] = "entered"
        except GateSpecError as e:
            out[i] = str(e)[:40]
            try:
                inside.abort()
            except Exception:  # noqa
                pass
    ts = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    [t.start() for t in ts]
    [t.join(10) for t in ts]
    return out


def verdict(exp, rec):
    try:
        return exp.score({"m": 1.0, "coverage_trace": rec}).verdict
    except GateSpecError as e:
        return str(e)[:110]


def summarize(tag, exp, cov, out, orig):
    rec = cov.record()
    print(f"[{tag}] workers: {out}")
    print(f"[{tag}] openings: {[o['calls'] for o in rec['sections'].get('G', [])]}")
    print(f"[{tag}] problems: {[p[:60] for p in rec['problems']]}")
    print(f"[{tag}] leftover: {state()}  code restored: "
          f"{ {k: fn.__code__ is c for k, (fn, c) in orig.items()} }")
    print(f"[{tag}] score: {verdict(exp, rec)}")


def A():
    write_mod("rt4v_a", "def f(): return 1\n")
    exp = make_exp(["rt4v_a:f"])
    cov = coverage_trace(exp)
    with cov:
        try:
            with cov:
                pass
        except GateSpecError as e:
            print("[A] second enter:", str(e)[:70])
        m = sys.modules["rt4v_a"]
        cov.run("G", m.f)
    print("[A] problems:", [p[:40] for p in cov.record()["problems"]], "leftover:", state())
    print("[A] score:", verdict(exp, cov.record()))


def B():
    write_mod("rt4v_b", """
        import time
        time.sleep(0.3)          # e.g. reading a config / model file at import
        def f(): return 1
    """)
    exp = make_exp(["rt4v_b:f"])
    cov = coverage_trace(exp)
    out = race(cov, lambda: sys.modules["rt4v_b"].f())
    m = sys.modules["rt4v_b"]
    summarize("B", exp, cov, out, {"f": (m.f, m.f.__code__)})


def C():
    write_mod("rt4v_c", "def f(): return 1\ndef g(): return 2\n")
    import rt4v_c
    exp = make_exp(["rt4v_c:f", "rt4v_c:g"])
    orig = {"f": (rt4v_c.f, rt4v_c.f.__code__)}
    n_both = 0
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    first = None
    for i in range(N):
        cov = coverage_trace(exp)
        out = race(cov, lambda: (rt4v_c.f(), rt4v_c.g()))
        if list(out.values()) == ["entered", "entered"]:
            n_both += 1
            if first is None:
                first = i
                summarize("C", exp, cov, out, orig)
        # reset leaked globals so attempts are independent
        P._THREADS.clear(); P._ANCHORS.clear(); P._MINTED.clear(); P._BY_FN.clear()
        P._ACTIVE = 0
        rt4v_c.f.__code__ = orig["f"][1]
    print(f"[C] both-entered in {n_both}/{N} attempts (module pre-imported, "
          f"switchinterval={sys.getswitchinterval()})")


def D():
    write_mod("rt4v_d", """
        import time
        def _lazy_f(): return 1
        _CACHE = {}
        def __getattr__(name):         # PEP 562 lazy export (V10 shape), does I/O on lookup
            if name == "f":
                time.sleep(0.2)
                return _lazy_f
            raise AttributeError(name)
    """)
    import rt4v_d
    exp = make_exp(["rt4v_d:f"])
    outer_exp = make_exp(["rt4v_d:f"], section="H")
    orig = {"f": (rt4v_d._lazy_f, rt4v_d._lazy_f.__code__)}
    outer = coverage_trace(outer_exp)
    with outer:                         # a legitimate enclosing trace on the main thread
        cov = coverage_trace(exp)
        out = race(cov, lambda: rt4v_d._lazy_f())
    summarize("D", exp, cov, out, orig)


def E():
    write_mod("rt4v_e", """
        import threading
        GATE = threading.Event()
        SLOW = set()
        def _lazy_f(): return 1
        def __getattr__(name):
            if name == "f":
                if threading.get_ident() in SLOW:
                    GATE.wait(5)       # this thread is descheduled here (simulated)
                return _lazy_f
            raise AttributeError(name)
    """)
    import rt4v_e
    exp = make_exp(["rt4v_e:f"])
    cov = coverage_trace(exp)
    orig = {"f": (rt4v_e._lazy_f, rt4v_e._lazy_f.__code__)}
    res = {}

    def slow():
        rt4v_e.SLOW.add(threading.get_ident())
        try:
            with cov:
                res["t2_state_inside"] = cov._state
                cov.run("G", rt4v_e._lazy_f)
            res["t2"] = "entered"
        except GateSpecError as e:
            res["t2"] = str(e)[:50]
    t2 = threading.Thread(target=slow)
    t2.start()
    time.sleep(0.2)                     # t2 has passed the state check and waits in resolution
    with cov:
        cov.run("G", rt4v_e._lazy_f)
    res["t1_after_exit_state"] = cov._state
    rt4v_e.GATE.set()
    t2.join(10)
    print("[E]", res)
    summarize("E", exp, cov, {"t2": res.get("t2")}, orig)


if __name__ == "__main__":
    print(sys.version.split()[0])
    {"A": A, "B": B, "C": C, "D": D, "E": E}[sys.argv[1]]()
