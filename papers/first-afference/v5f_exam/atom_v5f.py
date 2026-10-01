"""atom_v5f.py: G_ATOM, the premise gate (dynamic, frozen), written by the exam author from the v5f text
("Companion gates", G_ATOM; M10's G_ATOM interface; M7 "One-call steps").

It reads only the G_ATOM interface (_ANCHORS, _TOOL, _TOOL_NAME, _CONSUME, _list, _Opening, _Core, _EVENTS5,
_CALLBACKS5, _LOCAL, _LOST) and _v5_faultpoints(); it calls each step as FunctionType(code, vars(module)); it
binds the machinery with one `with coverage_trace(EXP): pass`; it reads and writes sys.monitoring directly.

Instruments, armed around each step call: tool id 5 with global PY_START and local CALL, C_RETURN, C_RAISE on
the step's code (the consumer's CALL opens the interval, its C_RETURN or C_RAISE closes it); an audit hook
(events on the step's thread); sys.setprofile (c_calls from the step's own frame). The harness's own code, and
its own interference in the split cases, are excluded.

The matrix (67 cases): _unwind_on 24, _unwind_off 24, _take 3, _set_local 4, _register 12; criteria (a)
interval, (b) inside, (c) outside, (d) state; the slots check once per run.
Controls: K1-K3 (instrument, in this run); K4-K14 (hookup: G_ATOM on ref_v5f.py + one frozen step patch, each in
a fresh process, must FAIL; K12 and K12b reported, not gated); parts A, B, E, D2 (reference pipelines built like
the steps, with count floors and T_MAX = 60 s) and R (the recursion sweep on the implementation's steps, with
K7's _unwind_off as its control). No void run: every outcome is PASS or FAIL.
Revision 13 (GAP-59, GAP-60): parts A, B, E and D2 as the text now states them in full (part A's CALL+C_RETURN
floor 18; part E's harness with its yields); K4's expected result is the failed binding enter (MONITOR_BUSY).

Usage: python atom_v5f.py [--impl PATH] [--deps DIR] [--out RESULT.json]
       python atom_v5f.py --impl PATH --matrix          (the matrix only; used for the hookup controls)
"""
import ast, gc, itertools, json, operator, os, platform, signal, subprocess, sys, tempfile, threading, time, types
from types import FunctionType

HERE = os.path.dirname(os.path.abspath(__file__))
ARGV = list(sys.argv)
if HERE not in sys.path:
    sys.path.append(HERE)
import v5f_tmp      # noqa: E402  temp dirs removed at exit; each hookup child's TMPDIR removed when it returns
T_MAX = 60.0


def _opt(n, d=None):
    return ARGV[ARGV.index(n) + 1] if n in ARGV else d


IMPL = os.path.abspath(_opt("--impl", os.path.join(HERE, "ref_v5f.py")))
DEPS = _opt("--deps", os.environ.get("V5F_DEPS_PATH"))
MON = sys.monitoring
EV = MON.events
PY_UNWIND = EV.PY_UNWIND
ITOOL = 5                         # the instrument
RTOOL = 2                         # the reference pipelines' tool (parts A, B, E, D2)

# ---------------------------------------------------------------------------------------------------
# loading the implementation (through the exam runner's fixtures; one enter and exit through the public API)
# ---------------------------------------------------------------------------------------------------
P = None
FIXFN = None


def load():
    global P, FIXFN
    sys.argv = [os.path.join(HERE, "run_protocol_v5f_exam.py"), "--impl", IMPL] + (["--deps-path", DEPS] if DEPS else [])
    sys.path.insert(0, HERE)
    import importlib
    R = importlib.import_module("run_protocol_v5f_exam")
    P = R.P
    with P.coverage_trace(R.EXP("F")):
        pass
    FIXFN = R.fx_gfi.h                                  # a fixture function's code for _set_local's cases
    return R


def step(name):
    return FunctionType(P._v5_faultpoints()[name], vars(P))


def tool():
    return P._TOOL[0]


def give_back(t):
    """The id back to styxx: freed, re-taken under its name, its five callbacks registered, events clear."""
    try:
        MON.set_events(t, 0)
    except ValueError:
        pass
    if MON.get_tool(t) is not None:
        MON.free_tool_id(t)
    MON.use_tool_id(t, P._TOOL_NAME)
    for e, cb in zip(P._EVENTS5, P._CALLBACKS5):
        MON.register_callback(t, e, cb)
    MON.set_events(t, 0)


def other_takes(t, name="atom-other"):
    MON.set_events(t, 0)
    MON.free_tool_id(t)
    MON.use_tool_id(t, name)


def read_callbacks(t):
    out = []
    for e in P._EVENTS5:
        prev = MON.register_callback(t, e, None)          # read by exchange and restore
        MON.register_callback(t, e, prev)
        out.append(prev)
    return out


def opening(armed=False, register=True):
    core = P._Core.__new__(P._Core)
    core.flags = {}
    o = P._Opening.__new__(P._Opening)
    o.core, o.frame, o.armed = core, object(), armed
    if register:
        P._ANCHORS[o.frame] = o
    return o

# ---------------------------------------------------------------------------------------------------
# the instruments
# ---------------------------------------------------------------------------------------------------
REC = {"on": False}
HARNESS = set()
ALLOWED_CALLS = (map, filter, itertools.chain, itertools.compress, itertools.repeat, itertools.tee,
                 itertools.chain.from_iterable)


def _harness_codes():
    def add(c):
        if c in HARNESS:
            return
        HARNESS.add(c)
        for k in c.co_consts:
            if isinstance(k, types.CodeType):
                add(k)
    for v in list(globals().values()):
        if isinstance(v, FunctionType) and v.__module__ == __name__:
            add(v.__code__)
        elif isinstance(v, type) and v.__module__ == __name__:
            for x in vars(v).values():
                if isinstance(x, FunctionType):
                    add(x.__code__)


def snapshot(t, code, cores):
    owner = MON.get_tool(t)
    return {"anchors": sorted((id(k), id(v)) for k, v in list(P._ANCHORS.items())),
            "owner": owner if owner is None or type(owner) is str else repr(owner),
            "events": MON.get_events(t) if owner is not None else None,
            "local": MON.get_local_events(t, code) if (owner is not None and code is not None) else None,
            "flags": [dict(c.flags) for c in cores], "lost": len(P._LOST)}


def _on_pystart(code, off):
    r = REC
    if not r["on"] or r["ign"] or threading.get_ident() != r["tid"]:
        return
    if code is r["code"] or code in HARNESS:
        return
    r["pystart"].append((code.co_qualname if hasattr(code, "co_qualname") else code.co_name, r["open"]))


def _on_call(code, off, callable, arg0):
    r = REC
    if not r["on"] or code is not r["code"]:
        return
    r["ign"] += 1
    try:
        r["calls"].append((callable, r["closed"] > 0))
        if callable is r["consumer"]:
            r["opened"] += 1
            r["state_at_open"] = snapshot(r["t"], r["lcode"], r["cores"])
            r["open"] = True
    finally:
        r["ign"] -= 1


def _on_cret(code, off, callable, arg0):
    r = REC
    if not r["on"] or code is not r["code"]:
        return
    if callable is r["consumer"] and r["open"]:
        r["open"] = False
        r["closed"] += 1


def _audit(ev, args):
    r = REC
    if not r.get("on") or r["ign"] or threading.get_ident() != r["tid"]:
        return
    if not r["open"]:
        return
    r["audit"].append(ev)
    split = r.get("split")
    if split and ev == "sys.monitoring.register_callback":
        r["rc"] += 1
        if r["rc"] == split:
            r["ign"] += 1
            try:
                th = threading.Thread(target=r["interfere"])
                th.start()
                th.join()
            finally:
                r["ign"] -= 1


def _prof(frame, event, arg):
    r = REC
    if r["on"] and not r["ign"] and event == "c_call" and frame.f_code is r["code"]:
        r["c_calls"].append(arg)


_INSTALLED = []


def install():
    if _INSTALLED:
        return
    _harness_codes()
    MON.use_tool_id(ITOOL, "atom-instrument")
    MON.register_callback(ITOOL, EV.PY_START, _on_pystart)
    MON.register_callback(ITOOL, EV.CALL, _on_call)
    MON.register_callback(ITOOL, EV.C_RETURN, _on_cret)
    MON.register_callback(ITOOL, EV.C_RAISE, _on_cret)
    sys.addaudithook(_audit)
    _INSTALLED.append(True)


def measure(fn, args, consumer, t, lcode=None, cores=(), split=None, interfere=None):
    """-> (result or exception, rec, pre, post)"""
    code = fn.__code__
    pre = snapshot(t, lcode, cores)
    REC.clear()
    REC.update({"on": False, "ign": 0, "tid": threading.get_ident(), "code": code, "consumer": consumer, "t": t,
                "lcode": lcode, "cores": cores, "calls": [], "opened": 0, "closed": 0, "open": False,
                "pystart": [], "audit": [], "c_calls": [], "state_at_open": None, "split": split, "rc": 0,
                "interfere": interfere})
    MON.set_local_events(ITOOL, code, EV.CALL | EV.C_RETURN | EV.C_RAISE)
    MON.set_events(ITOOL, EV.PY_START)
    sys.setprofile(_prof)
    REC["on"] = True
    try:
        out = ("ret", fn(*args))
    except BaseException as e:                              # noqa: BLE001
        out = ("exc", e)
    REC["on"] = False
    sys.setprofile(None)
    MON.set_events(ITOOL, 0)
    MON.set_local_events(ITOOL, code, 0)
    post = snapshot(t, lcode, cores)
    return out, dict(REC), pre, post


def _is_fi(c):
    """itertools.chain.from_iterable: a classmethod, so each read is a new bound object; compared as one."""
    return (type(c) is types.BuiltinMethodType and getattr(c, "__self__", None) is itertools.chain
            and c.__name__ == "from_iterable")


def criteria(rec, pre, exchanges=0, register=False):
    bad = []
    if rec["opened"] != 1 or rec["closed"] != 1:
        bad.append(f"(a) interval opened {rec['opened']}, closed {rec['closed']}")
    ins = [p for p in rec["pystart"] if p[1]]
    outs = [p for p in rec["pystart"] if not p[1]]
    if ins:
        bad.append(f"(b) PY_START inside: {ins[:3]}")
    aud = list(rec["audit"])
    if register:
        n = aud.count("sys.monitoring.register_callback")
        if n != exchanges:
            bad.append(f"(b) {n} register_callback audit events, the case makes {exchanges}")
        aud = [a for a in aud if a != "sys.monitoring.register_callback"]
    if aud:
        bad.append(f"(b) audit events inside: {aud[:3]}")
    if outs:
        bad.append(f"(c) PY_START outside: {outs[:3]}")
    cc = [c for c in rec["c_calls"] if not (c is rec["consumer"] or _is_fi(c) or c is itertools.tee)]
    if cc:
        bad.append(f"(c) c_calls from the step's frame: {[getattr(c, '__qualname__', repr(c)) for c in cc][:3]}")
    for c, after in rec["calls"]:
        if not (c is rec["consumer"] or _is_fi(c) or any(c is a for a in ALLOWED_CALLS)):
            bad.append(f"(c) CALL of {getattr(c, '__qualname__', repr(c))}")
            break
        if after:
            bad.append(f"(c) CALL of {getattr(c, '__qualname__', repr(c))} after the interval closed")
            break
    if rec["opened"] and rec["state_at_open"] != pre:
        bad.append("(d) state at the consumer's CALL differs from the state before the step")
    return bad

# ---------------------------------------------------------------------------------------------------
# the matrix
# ---------------------------------------------------------------------------------------------------
def case_unwind_on(named, reg, ev_set, other):
    t = tool()
    if not named:
        other_takes(t)
    o = opening(armed=False, register=reg)
    oth = None if other == "none" else opening(armed=(other == "armed"), register=True)
    MON.set_events(t, PY_UNWIND if ev_set else 0)
    cores = [o.core] + ([oth.core] if oth else [])
    out, rec, pre, post = measure(step("_unwind_on"), (o,), P._CONSUME, t, None, cores)
    bad = criteria(rec, pre)
    exp = dict(pre)
    if named and reg:
        exp["events"] = PY_UNWIND
        if not ev_set:
            exp["flags"] = [{"UNWIND_LOST": True} if oo.armed else {} for oo in [o] + ([oth] if oth else [])]
    if out[0] == "exc":
        bad.append(f"raised {out[1]!r}")
    if post != exp:
        bad.append(f"(d) effect: got {post}, expected {exp}")
    P._ANCHORS.clear()
    give_back(t)
    return bad


def case_unwind_off(named, keyk, left, ev_set):
    t = tool()
    if not named:
        other_takes(t)
    o = opening(register=True) if keyk == "registered" else None
    key = o.frame if o else (object() if keyk == "unregistered" else None)
    if left:
        opening(register=True)
    MON.set_events(t, PY_UNWIND if ev_set else 0)
    out, rec, pre, post = measure(step("_unwind_off"), (key,), P._CONSUME, t)
    bad = criteria(rec, pre)
    exp = dict(pre)
    anchors = [a for a in pre["anchors"] if not (o is not None and a[0] == id(key))]
    exp["anchors"] = anchors
    if named and not anchors:
        exp["events"] = 0
    if out[0] == "exc":
        bad.append(f"raised {out[1]!r}")
    if post != exp:
        bad.append(f"(d) effect: got {post}, expected {exp}")
    P._ANCHORS.clear()
    give_back(t)
    return bad


def case_take(state):
    t = tool()
    MON.set_events(t, 0)
    MON.free_tool_id(t)
    if state == "other":
        MON.use_tool_id(t, "atom-other")
    elif state == "styxx":
        MON.use_tool_id(t, P._TOOL_NAME)
    out, rec, pre, post = measure(step("_take"), (t,), P._CONSUME, t)
    bad = criteria(rec, pre)
    exp = dict(pre)
    if state == "unowned":
        exp["owner"] = P._TOOL_NAME
        exp["events"] = 0
    if out[0] == "exc":
        bad.append(f"raised {out[1]!r}")
    if post != exp:
        bad.append(f"(d) effect: got {post}, expected {exp}")
    give_back(t)
    return bad


def case_set_local(named, events):
    t = tool()
    code = FIXFN.__code__
    if not named:
        other_takes(t)
    MON.set_local_events(t, code, 0 if events else P._LOCAL)
    out, rec, pre, post = measure(step("_set_local"), (t, code, events), P._CONSUME, t, code)
    bad = criteria(rec, pre)
    exp = dict(pre)
    if named:
        exp["local"] = events
    if out[0] == "exc":
        bad.append(f"raised {out[1]!r}")
    if post != exp:
        bad.append(f"(d) effect: got {post}, expected {exp}")
    MON.set_local_events(t, code, 0)
    give_back(t)
    return bad


class _FinCB:
    """A finalizer callable: returns None; its __del__ records whether the interval is open and len(_LOST)."""
    LOG = []

    def __call__(self, *a):
        return None

    def __del__(self):
        _FinCB.LOG.append((REC.get("open"), REC.get("closed"), len(P._LOST)))


def _other_cb(*a):
    return None


def case_register(kind, k=None):
    t = tool()
    ours = P._TOOL_NAME
    lost0 = len(P._LOST)
    other_cbs = [FunctionType(_other_cb.__code__, {}) for _ in range(5)]
    split, interfere, exchanges = None, None, 5
    if kind in ("replaced", "replaced_S"):
        MON.register_callback(t, PY_UNWIND, other_cbs[4])
    if kind in ("plain_S", "replaced_S"):
        MON.set_events(t, PY_UNWIND)
    if kind == "finalizer":
        _FinCB.LOG.clear()
        MON.register_callback(t, EV.PY_START, _FinCB())
        MON.register_callback(t, PY_UNWIND, _FinCB())
    if kind == "other":
        other_takes(t)
        exchanges = 0
    if kind == "unowned":
        MON.set_events(t, 0)
        MON.free_tool_id(t)
        exchanges = 0
    if kind == "split":
        split, exchanges = k, k

        def interfere():
            MON.free_tool_id(t)
            MON.use_tool_id(t, "atom-other")
            for e, cb in zip(P._EVENTS5, other_cbs):
                MON.register_callback(t, e, cb)
    out, rec, pre, post = measure(step("_register"), (t,), P._list, t, split=split, interfere=interfere)
    bad = criteria(rec, pre, exchanges, register=True)
    r = out[1] if out[0] == "ret" else None
    if out[0] == "exc":
        bad.append(f"raised {out[1]!r}")
    lost = len(P._LOST) - lost0
    if kind in ("plain", "plain_S"):
        want_r, want_lost = [ours], 0
    elif kind in ("replaced", "replaced_S"):
        want_r, want_lost = [None, ours], 1
    elif kind == "finalizer":
        want_r, want_lost = [None, None, ours], 2
    elif kind == "other":
        want_r, want_lost = ["atom-other"], 0
    elif kind == "unowned":
        want_r, want_lost = [None], 0
    else:
        want_r, want_lost = [None, "atom-other"], 1
    if not (type(r) is list and len(r) == len(want_r) and all(
            (x is y) if y is ours else (x == y) for x, y in zip(r, want_r))):
        bad.append(f"(d) result {r!r}, expected {['<name>' if y is ours else y for y in want_r]}")
    if lost != want_lost:
        bad.append(f"(d) len(_LOST) + {lost}, expected + {want_lost}")
    if kind in ("plain", "plain_S", "replaced", "replaced_S", "finalizer"):
        cbs = read_callbacks(t)
        if any(a is not b for a, b in zip(cbs, P._CALLBACKS5)):
            bad.append("(d) styxx's five callbacks not all in place afterwards")
        if kind.endswith("_S") and MON.get_events(t) != PY_UNWIND:
            bad.append(f"(d) the global events are {MON.get_events(t)} afterwards, not PY_UNWIND")
    if kind == "split":
        cbs = read_callbacks(t)
        mine = [i for i, (a, b) in enumerate(zip(cbs, P._CALLBACKS5)) if a is b]
        if mine != [k - 1]:
            bad.append(f"(d) styxx's callback in slots {mine} of the other tool's, expected [{k - 1}]")
    if kind == "finalizer":
        gc.collect()
        log = list(_FinCB.LOG)
        if len(log) != 2 or any(op for op, _, _ in log) or any(cl < 1 for _, cl, _ in log) \
                or any(n != lost0 + 2 for _, _, n in log):
            bad.append(f"(b) finalizers: {log} (each must run after the interval closed and see len(_LOST) + 2)")
    give_back(t)
    return bad


def matrix():
    res = {}
    for named in (True, False):
        for reg in (True, False):
            for ev in (True, False):
                for other in ("none", "armed", "unarmed"):
                    res[f"_unwind_on/{'named' if named else 'other'}/{'reg' if reg else 'unreg'}/"
                        f"{'S' if ev else 'clear'}/{other}"] = case_unwind_on(named, reg, ev, other)
    for named in (True, False):
        for keyk in ("registered", "unregistered", "None"):
            for left in (True, False):
                for ev in (True, False):
                    res[f"_unwind_off/{'named' if named else 'other'}/{keyk}/{'left' if left else 'last'}/"
                        f"{'S' if ev else 'clear'}"] = case_unwind_off(named, keyk, left, ev)
    for st in ("unowned", "other", "styxx"):
        res[f"_take/{st}"] = case_take(st)
    for named in (True, False):
        for events in (P._LOCAL, 0):
            res[f"_set_local/{'named' if named else 'other'}/{events}"] = case_set_local(named, events)
    for kind in ("plain", "replaced", "plain_S", "replaced_S", "finalizer", "other", "unowned"):
        res[f"_register/{kind}"] = case_register(kind)
    for k in range(1, 6):
        res[f"_register/split{k}"] = case_register("split", k)
    slots = {n: type(P._Opening.__dict__.get(n)) is types.MemberDescriptorType for n in ("armed", "core", "frame")}
    slots["_Core.flags"] = type(P._Core.__dict__.get("flags")) is types.MemberDescriptorType
    return res, slots

# ---------------------------------------------------------------------------------------------------
# instrument controls K1-K3 (the harness's own pipelines, compiled outside the harness)
# ---------------------------------------------------------------------------------------------------
KSRC = '''
def _pp_set_events(t, e):
    return SE(t, e)
def k1(t):
    _CONSUME(_map(_pp_set_events, (t,), (0,)))
class G:
    __slots__ = ("armed",)
    def __getattribute__(self, n):
        return object.__getattribute__(self, n)
def k2(o):
    _CONSUME(_map(_ARMED, (o,)))
def k3(t):
    _CONSUME(_map(_getframe, (0,)))
'''


def instrument_controls():
    ns = {"SE": MON.set_events, "_CONSUME": P._CONSUME, "_map": map, "_ARMED": operator.attrgetter("armed"),
          "_getframe": sys._getframe}
    exec(compile(KSRC, "<atom-controls>", "exec"), ns)
    t = RTOOL
    g = ns["G"].__new__(ns["G"])
    object.__setattr__(g, "armed", True)
    out = {}
    for k, fn, args in (("K1", ns["k1"], (t,)), ("K2", ns["k2"], (g,)), ("K3", ns["k3"], (t,))):
        _, rec, pre, _ = measure(fn, args, P._CONSUME, t)
        bad = criteria(rec, pre)
        out[k] = {"detected": any(b.startswith("(b)") for b in bad), "by": bad[:2]}
    return out

# ---------------------------------------------------------------------------------------------------
# the reference pipelines (parts A, B, E, D2): built like _unwind_on and _unwind_off, on tool RTOOL
# ---------------------------------------------------------------------------------------------------
A = {}
RNAME = "atom-ref"
_CONSUME = None
_map, _chain, _compress, _is, _not = map, itertools.chain, itertools.compress, operator.is_, operator.not_
_NONE1, _ZERO1, _PYU1, _RNAME1 = (None,), (0,), (PY_UNWIND,), (RNAME,)
REFSRC = '''
def clear_one(key):
    t, get_tool, set_events = RT, GT, SE
    _CONSUME(_chain(_map(A.pop, (key,), _NONE1),
                    _map(set_events, _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _RNAME1)),
                                               _map(_not, (A,))), _ZERO1)))
def clear_two(key):
    t, get_tool, set_events = RT, GT, SE
    A.pop(key, None)
    if get_tool(t) is RNAME and not A:
        set_events(t, 0)
def clear_pycall(key):
    t, get_tool, set_events = RT, GT, SE
    A.pop(key, None)
    if get_tool(t) is RNAME and not A:
        _py()
        set_events(t, 0)
def _py():
    return None
def open_one(key, o):
    t, get_tool, set_events = RT, GT, SE
    A[key] = o
    _CONSUME(_map(set_events, _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _RNAME1)),
                                        _map(_is, _map(A.get, (key,)), (o,))), _PYU1))
'''
REF = {}


def ref_pipelines():
    MON.use_tool_id(RTOOL, RNAME)
    import collections
    ns = {"RT": RTOOL, "GT": MON.get_tool, "SE": MON.set_events, "A": A, "RNAME": MON.get_tool(RTOOL),
          "_CONSUME": collections.deque(maxlen=0).extend, "_map": map, "_chain": itertools.chain,
          "_compress": itertools.compress, "_is": operator.is_, "_not": operator.not_, "_NONE1": (None,),
          "_ZERO1": (0,), "_PYU1": (PY_UNWIND,), "_RNAME1": (MON.get_tool(RTOOL),)}
    exec(compile(REFSRC, "<atom-reference>", "exec"), ns)
    REF.update(ns)
    return ns


def _ge():
    return MON.get_events(RTOOL) & PY_UNWIND


def part_a():
    """One trial per event an instrument delivers inside the clearing function; each registers an anchor."""
    res = {}
    for form in ("clear_one", "clear_two"):
        fn = REF[form]
        code = fn.__code__
        for inst in ("INSTRUCTION", "CALL+C_RETURN", "BRANCH", "setprofile", "opcode"):
            def run(trial):
                A.clear()
                k0 = object()
                A[k0] = 1
                MON.set_events(RTOOL, PY_UNWIND)
                st = {"n": 0, "reg": []}

                def hit():
                    if st["n"] == trial:
                        k = object()
                        A[k] = 1
                        st["reg"].append((k, bool(_ge())))
                    st["n"] += 1
                if inst in ("INSTRUCTION", "CALL+C_RETURN", "BRANCH"):
                    MON.use_tool_id(1, "atom-parta") if MON.get_tool(1) is None else None
                    evs = {"INSTRUCTION": EV.INSTRUCTION, "CALL+C_RETURN": EV.CALL | EV.C_RETURN | EV.C_RAISE,
                           "BRANCH": EV.BRANCH}[inst]
                    for e in (EV.INSTRUCTION, EV.CALL, EV.C_RETURN, EV.BRANCH):
                        MON.register_callback(1, e, (lambda *a: hit()) if e & evs else None)
                    MON.register_callback(1, EV.C_RAISE, None)          # set with C_RETURN, never counted
                    MON.set_local_events(1, code, evs)
                    fn(k0)
                    MON.set_local_events(1, code, 0)
                elif inst == "setprofile":
                    def prof(frame, event, arg):
                        if frame.f_code is code:
                            hit()
                    sys.setprofile(prof)
                    fn(k0)
                    sys.setprofile(None)
                else:
                    def local(frame, event, arg):
                        hit()
                        return local

                    def glob(frame, event, arg):
                        if frame.f_code is code:
                            frame.f_trace_opcodes = True
                            frame.f_trace = local
                            sys.settrace(glob)          # 3.12.3 applies f_trace_opcodes only on re-instrumentation
                            return local
                        return None
                    sys.settrace(glob)
                    fn(k0)
                    sys.settrace(None)
                viol = any(was_set for k, was_set in st["reg"] if k in A) and not _ge()
                return st["n"], viol
            n, _ = run(-1)
            v = sum(run(i)[1] for i in range(n))
            res[f"{form}/{inst}"] = {"trials": n, "violations": v}
    floors = {"INSTRUCTION": 40, "CALL+C_RETURN": 18, "setprofile": 3, "opcode": 40}   # revision 13: 18 (GAP-59)
    ok = all(res[f"clear_one/{i}"]["violations"] == 0 and res[f"clear_one/{i}"]["trials"] >= f
             and res[f"clear_two/{i}"]["violations"] >= 1 for i, f in floors.items())
    A.clear()
    MON.set_events(RTOOL, 0)
    return {"rows": res, "floors": floors, "pass": ok, "BRANCH": "reported, not evidence"}


def part_b():
    fn = REF["clear_one"]
    A.clear()
    k0 = object()
    A[k0] = 1
    seen = []

    def prof(frame, event, arg):
        if event == "c_call" and frame.f_code is fn.__code__:
            seen.append(arg)
    sys.setprofile(prof)
    fn(k0)
    sys.setprofile(None)
    ok = len(seen) == 1 and seen[0] is REF["_CONSUME"]
    return {"c_calls": [getattr(s, "__qualname__", repr(s)) for s in seen], "pass": ok}


def part_e(form, floor=50000, until_first=False):
    """Part E as revision 13 states the harness (GAP-59): four workers, each with its own pure-Python profile
    function that calls time.sleep(0) at every c_call whose frame's code is the close function's; each repeats
    k = object(); open_one(k, k); three times {a sample: "is the event clear?"; time.sleep(0)}; close(k);
    time.sleep(0). Counts go to the shared totals under a harness lock every 64 samples and when the worker
    stops. sys.setswitchinterval(1e-6) for the run, restored after it; the main thread polls every 5 ms."""
    close = REF[form]
    ccode = close.__code__
    opener = REF["open_one"]
    st = {"samples": 0, "clear": 0, "stop": False}
    lock = threading.Lock()

    def prof(frame, event, arg):
        if event == "c_call" and frame.f_code is ccode:
            time.sleep(0)

    def worker():
        sys.setprofile(prof)
        n = c = 0
        try:
            while not st["stop"]:
                k = object()
                opener(k, k)
                for _ in range(3):
                    c += not _ge()
                    n += 1
                    if n == 64:
                        with lock:
                            st["samples"] += n
                            st["clear"] += c
                        n = c = 0
                    time.sleep(0)
                close(k)
                time.sleep(0)
        finally:
            sys.setprofile(None)
            with lock:
                st["samples"] += n
                st["clear"] += c
    A.clear()
    MON.set_events(RTOOL, 0)
    old_si = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        ths = [threading.Thread(target=worker) for _ in range(4)]
        t0 = time.monotonic()
        for t in ths:
            t.start()
        while True:
            time.sleep(0.005)
            with lock:
                done = st["samples"] >= floor or (until_first and st["clear"])
            if done or time.monotonic() - t0 > T_MAX:
                break
        st["stop"] = True
        for t in ths:
            t.join()
    finally:
        sys.setswitchinterval(old_si)
        A.clear()
        MON.set_events(RTOOL, 0)
    secs = round(time.monotonic() - t0, 2)
    return {"form": form, "samples": st["samples"], "clear": st["clear"], "seconds": secs, "t_max_hit": secs > T_MAX}


def part_d2(form, floor=5000, until_first=False):
    close = REF[form]
    st = {"closing": False, "closes": 0, "interrupts": 0, "viol": 0, "reg": []}

    def reg():
        st["interrupts"] += 1
        if st["closing"]:
            k = object()
            A[k] = 1
            st["reg"].append((k, bool(_ge())))

    class Fin:
        def __del__(self):
            reg()

    def handler(sig, frm):
        reg()
    old = signal.signal(signal.SIGALRM, handler)
    thr = gc.get_threshold()
    gc.set_threshold(1)
    signal.setitimer(signal.ITIMER_REAL, 0.00002, 0.00002)
    t0 = time.monotonic()
    try:
        while True:
            A.clear()
            k0 = object()
            A[k0] = 1
            MON.set_events(RTOOL, PY_UNWIND)
            st["reg"] = []
            x = Fin()
            x.me = x
            del x
            st["closing"] = True
            close(k0)
            st["closing"] = False
            st["closes"] += 1
            if any(was for k, was in st["reg"] if k in A) and not _ge():
                st["viol"] += 1
            if until_first and st["viol"]:
                break
            if st["closes"] >= floor and (until_first or st["interrupts"] >= floor):
                break
            if time.monotonic() - t0 > T_MAX:
                break
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0, 0)
        signal.signal(signal.SIGALRM, old)
        gc.set_threshold(*thr)
        A.clear()
        MON.set_events(RTOOL, 0)
    return {"form": form, "closes": st["closes"], "interrupts": st["interrupts"], "violations": st["viol"],
            "seconds": round(time.monotonic() - t0, 2)}

# ---------------------------------------------------------------------------------------------------
# part R: the recursion sweep on the implementation's steps
# ---------------------------------------------------------------------------------------------------
def at_depth(n, f):
    if n <= 0:
        return f()
    return next(map(at_depth, (n - 1,), (f,)))


def _k7_unwind_off():
    src = patched_source("K7")
    tree = ast.parse(src)
    fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_unwind_off"][0]
    mod = ast.Module([fn], [])
    code = [c for c in compile(mod, "<K7>", "exec").co_consts if isinstance(c, types.CodeType)][0]
    return FunctionType(code, vars(P))


def r_setups(fn_name, fn):
    t = tool()
    code = FIXFN.__code__

    def prep():
        P._ANCHORS.clear()
        give_back(t)
        if fn_name == "_unwind_off":
            o = opening(register=True)
            MON.set_events(t, PY_UNWIND)
            return (o.frame,), lambda: (o.frame not in P._ANCHORS, MON.get_events(t) == 0), \
                lambda: (o.frame in P._ANCHORS, MON.get_events(t) == PY_UNWIND)
        if fn_name == "_unwind_on":
            o = opening(register=True)
            oth = opening(armed=True, register=True)
            MON.set_events(t, 0)
            return (o,), lambda: (MON.get_events(t) == PY_UNWIND, oth.core.flags.get("UNWIND_LOST") is True), \
                lambda: (MON.get_events(t) == 0, not oth.core.flags)
        if fn_name == "_take":
            MON.free_tool_id(t)
            return (t,), lambda: (MON.get_tool(t) is P._TOOL_NAME,), lambda: (MON.get_tool(t) is None,)
        MON.set_local_events(t, code, 0)
        return (t, code, P._LOCAL), lambda: (MON.get_local_events(t, code) == P._LOCAL,), \
            lambda: (MON.get_local_events(t, code) == 0,)

    def trial(n):
        args, full, none = prep()
        try:
            at_depth(n, lambda: fn(*args))
            raised = False
        except RecursionError:
            raised = True
        f, z = all(full()), all(none())
        out = "full" if f else ("none" if z else "partial")
        P._ANCHORS.clear()
        give_back(t)
        MON.set_local_events(t, code, 0)
        return raised, out
    return trial


def part_r():
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(100000)
    res, ok = {}, True
    try:
        steps = [(n, step(n)) for n in ("_unwind_off", "_unwind_on", "_take", "_set_local")] + \
                [("K7:_unwind_off", _k7_unwind_off())]
        for name, fn in steps:
            trial = r_setups(name.split(":")[-1], fn)
            lo, hi = 0, 20000
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if trial(mid)[0]:
                    hi = mid - 1
                else:
                    lo = mid
            n0 = lo
            outs = {"full": 0, "none": 0, "partial": 0, "bad": 0}
            for n in range(max(0, n0 - 30), n0 + 31):
                raised, out = trial(n)
                if (not raised and out == "full") or (raised and out == "none"):
                    outs["full" if not raised else "none"] += 1
                else:
                    outs["bad"] += 1
                    outs["partial"] += out == "partial"
            res[name] = {"n0": n0, **outs}
            if name.startswith("K7"):
                res[name]["detected"] = outs["partial"] >= 1
                ok &= res[name]["detected"]
            else:
                ok &= outs["bad"] == 0 and outs["full"] > 0 and outs["none"] > 0
    finally:
        sys.setrecursionlimit(old)
    return {"steps": res, "pass": ok}

# ---------------------------------------------------------------------------------------------------
# the hookup controls K4-K14: frozen text patches of ref_v5f.py
# ---------------------------------------------------------------------------------------------------
def _refcensus_controls():
    import runpy
    g = runpy.run_path(os.path.join(HERE, "refcensus_v5f.py"), run_name="refcensus_controls")
    return g["CONTROLS"], g["REG_OLD"]


UO_BODY = "    _CONSUME(_chain(_map(_ANCHORS.pop, (key,), _NONE1),\n"
UO_SET = ("        _map(set_events,\n             _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),\n"
          "                       _map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))),\n             _PYU1)))")
TAKE = "    _CONSUME(_map(use_tool_id, _compress((t,), _map(_is, _map(get_tool, (t,)), _NONE1)), _NAME1))"


def hookup_patches():
    ctl, reg_old = _refcensus_controls()
    k = {
        # K4: _register in revision 5's form: one name gate before all five exchanges, no owner read, no count
        "K4": [(reg_old, "    return _list(_map(register_callback, _chain.from_iterable(_map(_repeat, _compress((t,), "
                         "_map(_is, _map(get_tool, (t,)), _NAME1)), (5,))), _EVENTS5, _CALLBACKS5))")],
        # K5: _unwind_off through a Python helper (the classic split)
        "K5": [("def _unwind_off(key):\n", "def _unwind_off(key):\n    return _unwind_off_helper(key)\n\n\n"
                                           "def _unwind_off_helper(key):\n")],
        # K6: _unwind_off consumed by a deque built at call time
        "K6": [(UO_BODY, "    collections.deque(maxlen=0).extend(_chain(_map(_ANCHORS.pop, (key,), _NONE1),\n")],
        # K7: _unwind_off with the pop as its own statement before the consuming call
        "K7": [(UO_BODY, "    _ANCHORS.pop(key, None)\n    _CONSUME(_chain((),\n")],
        # K8: _unwind_on whose set is not gated on o's own anchor
        "K8": [(UO_SET, "        _map(set_events,\n             _compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),\n"
                        "             _PYU1)))")],
        # K9: _take with the unowned test as its own statement
        "K9": [(TAKE, "    free = get_tool(t) is None\n    _CONSUME(_map(use_tool_id, _compress((t,), (free,)), _NAME1))")],
        # K10: _register in revision 6's form, the count made after the consuming call
        "K10": [(reg_old, "    r = _list(_chain(_map(register_callback, _compress(_repeat(t), _map(_is, _map(get_tool, "
                          "_repeat(t, 5)), _repeat(_TOOL_NAME))), _EVENTS5, _CALLBACKS5), _map(get_tool, (t,))))\n"
                          "    _LOST.extend(_filter(None, _map(_is_not, r[:-1], _CALLBACKS5)))\n    return r")],
    }
    for n in ("K11", "K12", "K12b", "K13", "K14"):
        k[n] = ctl[n]
    return k


def patched_source(name):
    s = open(os.path.join(HERE, "ref_v5f.py"), encoding="utf-8").read()
    for a, b in hookup_patches()[name]:
        if s.count(a) != 1:
            raise SystemExit(f"hookup control {name}: a patch does not apply exactly once: {a[:70]!r}")
        s = s.replace(a, b)
    return s


def run_hookup(name):
    env = dict(os.environ)
    if DEPS:
        env["V5F_DEPS_PATH"] = DEPS
    with v5f_tmp.scratch(f"atom_{name}_") as d:
        p = os.path.join(d, "ref_v5f.py")
        open(p, "w", encoding="utf-8").write(patched_source(name))
        r = v5f_tmp.child_run([sys.executable, os.path.abspath(__file__), "--impl", p, "--matrix"],
                              capture_output=True, text=True, timeout=600, env=env)
    ln = [x for x in r.stdout.splitlines() if x.startswith("MATRIX ")]
    if not ln:
        return {"failed_cases": "all (the run did not complete)", "error": r.stderr.strip().splitlines()[-1:]}
    d = json.loads(ln[-1][7:])
    failed = {k: v for k, v in d["cases"].items() if v}
    return {"failed_cases": len(failed), "examples": dict(list(failed.items())[:2]), "slots_ok": all(d["slots"].values())}

# ---------------------------------------------------------------------------------------------------
def build():
    return {"sys.version": sys.version, "python_build": list(platform.python_build()),
            "python_compiler": platform.python_compiler()}


def main():
    load()
    install()
    if "--matrix" in ARGV:
        cases, slots = matrix()
        print("MATRIX " + json.dumps({"cases": cases, "slots": slots}, default=str))
        sys.stdout.flush()
        v5f_tmp.cleanup()                           # os._exit skips atexit
        os._exit(0)
    t0 = time.monotonic()
    res = {"impl": IMPL, "build": build()}
    cases, slots = matrix()
    failed = {k: v for k, v in cases.items() if v}
    res["matrix"] = {"cases": len(cases), "failed": failed, "slots": slots}
    res["K1-K3"] = instrument_controls()
    ref_pipelines()
    res["part_A"] = part_a()
    res["part_B"] = part_b()
    e1, e2 = part_e("clear_one"), part_e("clear_two", until_first=True)
    res["part_E"] = {"one_call": e1, "control": e2,
                     "pass": (e1["samples"] >= 50000 and e1["clear"] == 0 and not e1["t_max_hit"]
                              and e2["clear"] >= 1 and e2["samples"] < 50000 and not e2["t_max_hit"])}
    d1, d2, d3 = part_d2("clear_one"), part_d2("clear_pycall", until_first=True), part_d2("clear_two")
    res["part_D2"] = {"one_call": d1, "python_call_control": d2, "two_statement_reported": d3,
                      "pass": d1["closes"] >= 5000 and d1["interrupts"] >= 5000 and d1["violations"] == 0
                              and d2["violations"] >= 1 and d2["closes"] < 5000}
    res["part_R"] = part_r()
    hk = {}
    for name in ("K4", "K5", "K6", "K7", "K8", "K9", "K10", "K11", "K13", "K14", "K12", "K12b"):
        v5f_tmp.disk_guard(what=f"hookup control {name}")
        hk[name] = run_hookup(name)
        gated = name not in ("K12", "K12b")
        n = hk[name]["failed_cases"]
        hk[name]["gated"] = gated
        hk[name]["detected"] = (n if isinstance(n, int) else 1) > 0
        if name == "K4":                            # revision 13 (GAP-60): the expected result is the failed binding enter
            hk[name]["expected"] = "the binding enter refuses MONITOR_BUSY; the matrix never runs"
            hk[name]["as_expected"] = (not isinstance(n, int)) and "MONITOR_BUSY" in " ".join(hk[name].get("error", []))
    res["hookup"] = hk
    verdict = (not failed and all(slots.values()) and all(v["detected"] for v in res["K1-K3"].values())
               and res["part_A"]["pass"] and res["part_B"]["pass"] and res["part_E"]["pass"]
               and res["part_D2"]["pass"] and res["part_R"]["pass"]
               and all(v["detected"] for v in hk.values() if v["gated"]))
    res["G_ATOM"] = "PASS" if verdict else "FAIL"
    res["seconds"] = round(time.monotonic() - t0, 1)
    out = _opt("--out")
    if out:
        json.dump(res, open(out, "w"), indent=1, default=str)
    print(json.dumps({k: res[k] for k in ("G_ATOM", "seconds")}), json.dumps(res, default=str)[:4000])
    sys.stdout.flush()
    v5f_tmp.cleanup()                               # os._exit skips atexit
    os._exit(0 if verdict else 1)


if __name__ == "__main__":
    try:
        main()
    except v5f_tmp.DiskLow as e:
        rc = v5f_tmp.stop_disk_low(e)
        v5f_tmp.cleanup()
        sys.stdout.flush()
        os._exit(rc)
    finally:
        v5f_tmp.cleanup()
