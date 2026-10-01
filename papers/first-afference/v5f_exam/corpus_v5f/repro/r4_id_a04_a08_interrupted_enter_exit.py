"""round4/identity/r1/a04_enter_fails_after_mint.py and a08_interrupted_exit_poisons_entry.py, rewritten.
a04 (i): asyncio.events.Handle._run patched with a MagicMock while a tracer enters; then a later normal trace,
and the same tracer object entered again. (ii): an audit hook refusing object.__setattr__('__code__') on one
declared function while the tracer enters; (ii'): the same failure in an inner tracer while an innocent outer
tracer is active on the other function, the outer then exited and scored. a04 (iii) and a08 interrupted v5e's
__enter__/__exit__ at named lines of its private source; v5f's text defines the fault points instead
(_v5_faultpoints(), the harness rules' id-5 injector), so here the interruption is a KeyboardInterrupt at the
n-th instruction of the enter's (iii) or exit's (a08) fault-point code objects, n in 1, 5, 25, 100; each followed
by record() on the interrupted tracer, _v5_state(), and two later normal traces of the same target."""
import asyncio.events, sys
from unittest import mock

ENTER_KEYS = ("_CoverageTracer.__enter__", "_enter", "_enter_txn", "_resolve_target", "_mint", "_provenance")
EXIT_KEYS = ("_CoverageTracer.__exit__", "_exit", "_exit_txn", "_retire", "_reconcile", "_prune")


def main(api):
    out = {}
    m4 = api.fixture("rp_id_enter", "def f(x=0): return x\ndef g(x=0): return x\n")
    F, G = m4.f.__code__, m4.g.__code__
    e = api.exp({"G": ["rp_id_enter:f", "rp_id_enter:g"]})
    box = {}
    with mock.patch.object(asyncio.events.Handle, "_run"):
        out["i_construct"] = api.attempt(lambda: box.__setitem__("t", api.coverage_trace(e)))
        if "t" in box:
            out["i_enter"] = api.attempt(lambda: box["t"].__enter__() is box["t"])
            out["i_exit_after"] = api.attempt(lambda: bool(box["t"].__exit__(None, None, None)))
    tr1 = box.get("t") or api.coverage_trace(e)
    out["i_after"] = {"f_code_restored": m4.f.__code__ is F, "g_code_restored": m4.g.__code__ is G, "state": api.state()}
    out["i_later_normal"] = api.trace(api.exp({"G": ["rp_id_enter:f"]}), lambda c: c.run("G", m4.f, 1))
    out["i_after_later"] = {"f_code_restored": m4.f.__code__ is F, "state": api.state()}
    out["i_retry_same_tracer"] = api.attempt(lambda: tr1.__enter__() is tr1)
    if out["i_retry_same_tracer"].get("returned") is True:
        out["i_retry_run"] = api.attempt(tr1.run, "G", lambda: (m4.f(1), m4.g(1)) and None)
        out["i_retry_exit"] = api.attempt(lambda: bool(tr1.__exit__(None, None, None)))
    out["i_retry_record"] = api.record(tr1)
    m5 = api.fixture("rp_id_enter2", "def f(x=0): return x\ndef g(x=0): return x\n")
    m5b = api.fixture("rp_id_enter2b", "def f(x=0): return x\ndef g(x=0): return x\n")
    armed, target = [False], [m5.g]

    def audit(ev, args):
        if armed[0] and ev == "object.__setattr__" and len(args) >= 2 and args[1] == "__code__" and args[0] is target[0]:
            raise PermissionError("sandbox audit hook: __code__ writes on this function are not allowed")
    sys.addaudithook(audit)
    F5 = m5.f.__code__
    t = api.coverage_trace(api.exp({"G": ["rp_id_enter2:f", "rp_id_enter2:g"]}))
    armed[0] = True
    out["ii_enter"] = api.attempt(lambda: t.__enter__() is t)
    armed[0] = False
    out["ii_exit"] = api.attempt(lambda: bool(t.__exit__(None, None, None)))
    out["ii_after"] = {"f_code_restored": m5.f.__code__ is F5, "state": api.state()}
    F5b = m5b.f.__code__
    outer = api.coverage_trace(api.exp({"O": ["rp_id_enter2b:f"]}))
    r = {"outer_enter": api.attempt(lambda: outer.__enter__() is outer), "outer_run": api.attempt(outer.run, "O", m5b.f, 1)}
    inner = api.coverage_trace(api.exp({"I": ["rp_id_enter2b:f", "rp_id_enter2b:g"]}))
    target[0] = m5b.g
    armed[0] = True
    r["inner_enter"] = api.attempt(lambda: inner.__enter__() is inner)
    armed[0] = False
    r["inner_exit"] = api.attempt(lambda: bool(inner.__exit__(None, None, None)))
    r["outer_exit"] = api.attempt(lambda: bool(outer.__exit__(None, None, None)))
    r["outer_record"] = api.record(outer)
    r["f_code_restored"] = m5b.f.__code__ is F5b
    r["state"] = api.state()
    out["ii_prime"] = r
    for phase, keys in (("iii_enter", ENTER_KEYS), ("a08_exit", EXIT_KEYS)):
        for n in (1, 5, 25, 100):
            mod = api.fixture(f"rp_id_{phase}_{n}", "def f(x=0): return x\n")
            e = api.exp({"G": [f"rp_id_{phase}_{n}:f"]})
            tr = api.coverage_trace(e)
            r = {}
            disarm = None
            try:
                if phase == "iii_enter":
                    disarm = api.inject(keys, n)
                    try:
                        tr.__enter__()
                    finally:
                        r["injector"] = disarm()
                        disarm = None
                    tr.run("G", mod.f, 1)
                    tr.__exit__(None, None, None)
                else:
                    tr.__enter__()
                    tr.run("G", mod.f, 1)
                    disarm = api.inject(keys, n)
                    try:
                        tr.__exit__(None, None, None)
                    finally:
                        r["injector"] = disarm()
                        disarm = None
                r["raised"] = None
            except BaseException as ex:                # noqa: BLE001
                r["raised"] = type(ex).__name__
                if disarm is not None:
                    r["injector"] = disarm()
            r["record"] = api.record(tr)
            r["state"] = api.state()
            r["later"] = [api.trace(e, lambda c: c.run("G", mod.f, 1)) for _ in range(2)]
            r["state_after_later"] = api.state()
            out[f"{phase}_{n}"] = r
    return out
