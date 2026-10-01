# rev13 (GAP-54, GAP-61): a witness for each SM1 row the exam author found UNWITNESSED on 3.12.3, or the
# evidence for its EQUIVALENT_BY_SPEC filing. Each witness runs on v5f_exam/ref_v5f.py (read only) and on the
# row's weakening (the exam author's patch from v5f_exam/weakenings_v5f.py, or revision 13's re-targeted patch),
# one fresh subprocess per (witness, variant). Run: <venv3.12|venv3.13>/bin/python p_sm1.py [witness ...]
import hashlib, json, os, runpy, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
EXAM = os.path.join(HERE, '..', '..', 'v5f_exam')
REF = os.path.join(EXAM, 'ref_v5f.py')
W = {r['id']: r['patches'] for r in runpy.run_path(os.path.join(EXAM, 'weakenings_v5f.py'), run_name='w')['CATALOG']}
OLDCAP = '''        _map(_setitem, _map(_FLAGS, _filter(_ARMED, _chain.from_iterable(_map(_VALUES,
            _compress(_compress(_compress((_ANCHORS,), _map(_is, _map(get_tool, (t,)), _NAME1)),
                                _map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))),
                      _map(_not, _map(_and, _map(get_events, (t,)), _PYU1))))))), _LOST_KEY, _TRUE),'''
NEWCAP = OLDCAP.replace('_map(_not, _map(_and, _map(get_events, (t,)), _PYU1))', '(was_clear,)')
STMT1 = '    t, get_tool, get_events, set_events = _TOOL[0], _MON[0][0], _MON[0][1], _MON[0][2]\n    _CONSUME(_chain(\n'
MUT = {
 'spec': [],
 # revision 13's re-targeted form of A_capture_outside (revision 5's MF2 mutant): the event is read in its own
 # statement before the one call, and the capture is gated on that stale read
 'R13_capture_stale_read': [(STMT1, STMT1.replace('    _CONSUME(_chain(\n', '    was_clear = not (get_events(t) & PY_UNWIND)\n    _CONSUME(_chain(\n')),
                            (OLDCAP, NEWCAP)],
}
WALK_OLD = ('''    r = _GUARD["hint"]
    n = r.succ.get("next")
    while n is not None:
        r = n
        n = r.succ.get("next")
    return {''')
WALK_NEW = ('''    r = _GUARD["hint"]
    seen = {id(r)}
    n = r.succ.get("next")
    while n is not None and id(n) not in seen:
        seen.add(id(n))
        r = n
        n = r.succ.get("next")
    return {''')
GUARD_OLD = '''        "guard": "free" if r.tid is None else ("held" if _alive(r) else "dead"),'''
GUARD_NEW = '''        "guard": "cycle" if n is not None else ("free" if r.tid is None else ("held" if _alive(r) else "dead")),'''
# revision 13 (GAP-64): _v5_state() is total; its walk stops at the first repeated token and reports "cycle"
MUT['R13_total_walk'] = [(WALK_OLD, WALK_NEW), (GUARD_OLD, GUARD_NEW)]
for rid in ('A_binding_first_only', 'A_verified_widened', 'A_txn_shared_succ',
            'A_coh_no_file_skip', 'A_cache_callee_identity', 'A_alias_by_name', 'A_mint_eq', 'A_visible_deleted',
            'A_publish_recheck', 'A_enter_claim', 'A_exit_claim', 'A_atfork_handler', 'A_pid_passthrough',
            'A_unwind_on_recheck', 'A_detach_anchor_first', 'A_capture_outside', 'A_ensure_no_reclaim',
            'A_open_audited_after_append', 'M3_register_before_append', 'M5_exit_claim_not_idempotent'):
    MUT[rid] = W[rid]

FIX = r'''
import functools, threading
def f(x=0): return x + 1
def h(x=0): return x + 3
g = type(f)(f.__code__.replace(), globals(), 'g', (0,))  # V74: a declared function whose code equals f's
def blk(inside, go):
    inside.set(); go.wait(10); return 0
def real(x=0): return x + 7
def _mk_wrapped():                                       # X26g: a wraps wrapper whose globals carry no __file__
    ns = {'__name__': 'fx_r13'}
    exec(compile("def wrapped_g(x=0):\n    return x + 7\n", "/nonexistent/fx_other.py", "exec"), ns)
    w = ns['wrapped_g']; w.__wrapped__ = real; return w
wrapped_g = _mk_wrapped()
def _stamp(x=0): return x
power2 = functools.wraps(_stamp)(functools.lru_cache(None)(lambda x: x * 2))   # X24g: callee is a lambda
cached = functools.lru_cache(None)(lambda x: x * 3)                            # V07b
cached_alias = cached
'''
SETUP = r'''
import sys, os, json, gc, threading, types, importlib.util, dis
WORK, SRC = sys.argv[1], sys.argv[2]
sys.path.insert(0, os.path.dirname(SRC))
spec = importlib.util.spec_from_file_location("ref_v5f", SRC)
P = importlib.util.module_from_spec(spec); sys.modules["ref_v5f"] = P; spec.loader.exec_module(P)
sys.path.insert(0, os.path.join(WORK, "fx")); import fx_r13 as fx
M = sys.monitoring; E = M.events
def EXP(k): return P.Experiment(os.path.join(WORK, "repo", "PREREG_%s.md" % k))
def code(e):
    s = str(e); return s[s.index("[V5:")+4:s.index("]")] if "[V5:" in s else type(e).__name__
def score(k, rec):
    try: v = EXP(k).score({"m": 1.0, "coverage_trace": rec}); return ["PASS", v.coverage]
    except P.GateSpecError as e: return ["REFUSE", code(e)]
def notes(rec):
    return sorted({n.split("]")[0] + "]" for ops in rec["sections"].values() for o in ops for n in o["notes"]})
def out(x): print(json.dumps(x, default=str)); sys.stdout.flush(); os._exit(0)
FP = P._v5_faultpoints()
def sweep(code, ident, on_kth, run_trial, kmax=2000):
    """Instruction sweep: trial k runs run_trial(); at T's k-th INSTRUCTION in code, on_kth() runs. Stops at the
    first trial in which T executes fewer than k instructions of code, or when run_trial returns a violation."""
    res = []
    for k in range(1, kmax):
        st = {"n": 0, "fired": False}
        def cb(c, off):
            if c is code and threading.get_ident() == ident[0]:
                st["n"] += 1
                if st["n"] == k and not st["fired"]:
                    st["fired"] = True; on_kth()
        M.use_tool_id(5, "p_sm1-sweep"); M.register_callback(5, E.INSTRUCTION, cb); M.set_local_events(5, code, E.INSTRUCTION)
        try: v = run_trial()
        finally:
            M.set_local_events(5, code, 0); M.register_callback(5, E.INSTRUCTION, None); M.free_tool_id(5)
        if not st["fired"]: break
        res.append(v)
    return res
'''
CASES = {}
CASES['X26g'] = r'''
try:
    with P.coverage_trace(EXP("wrapped_g")) as cov: cov.run("G", fx.wrapped_g, 1)
    out(score("wrapped_g", cov.record()))
except P.GateSpecError as e: out(["RAISE", code(e)])
'''
CASES['X24g'] = r'''
try:
    with P.coverage_trace(EXP("power2")) as cov: cov.run("G", fx.power2, 1)
    out(score("power2", cov.record()))
except P.GateSpecError as e: out(["RAISE", code(e)])
'''
CASES['V07b'] = r'''
try:
    with P.coverage_trace(EXP("cached")) as cov: cov.run("G", fx.cached, 1)
    out(score("cached", cov.record()))
except P.GateSpecError as e: out(["RAISE", code(e)])
'''
CASES['V74'] = r'''
with P.coverage_trace(EXP("fg")) as cov:
    def sec(): fx.f(); fx.g(); fx.g()
    cov.run("G", sec)
rec = cov.record()
out({"union": {k: v for o in rec["sections"]["G"] for k, v in o["calls"].items()}, "score": score("fg", rec)})
'''
CASES['V36c'] = r'''
keep = []
with P.coverage_trace(EXP("f")) as cov:
    def sec():
        fx.f(); gc.freeze()                      # the count rises after the mint
        keep.append([fx.f.__code__])             # made after the freeze: a visible, tracked referrer of M_T
    cov.run("G", sec)
gc.unfreeze(); gc.collect()
out(score("f", cov.record()))
'''
CASES['X71d'] = r'''
p = P.coverage_trace(EXP("blk")); q = P.coverage_trace(EXP("blk")); p.__enter__(); q.__enter__()
inside, go = threading.Event(), threading.Event()
t = threading.Thread(target=lambda: p.run("G", fx.blk, inside, go)); t.start(); inside.wait(10)
p.__exit__(None, None, None)                     # P's credit stop while blk's entry is pending
go.set(); t.join(10); q.__exit__(None, None, None)
rec = p.record()
out({"P_calls": [o["calls"] for o in rec["sections"]["G"]], "P_score": score("blk", rec)})
'''
CASES['X32e'] = r'''
ident = [None]; succ = []
def trial():
    cov = P.coverage_trace(EXP("f")); res = []
    def t2():
        try: cov.__enter__(); res.append("ok")
        except P.GateSpecError as e: res.append(code(e))
    def interfere():
        th = threading.Thread(target=t2); th.start(); th.join(10)
    st["interfere"] = interfere
    def t1():
        ident[0] = threading.get_ident()
        try: cov.__enter__(); res.append("ok")
        except P.GateSpecError as e: res.append(code(e))
    th = threading.Thread(target=t1); th.start(); th.join(20)
    if "ok" in res: cov.__exit__(None, None, None)
    return tuple(sorted(res))
st = {}
r = sweep(FP["_enter"], ident, lambda: st["interfere"](), trial, kmax=600)
out({"trials": len(r), "trials_with_two_enters": sum(1 for x in r if x.count("ok") == 2),
     "trials_with_one": sum(1 for x in r if x.count("ok") == 1), "outcomes": sorted({"+".join(x) for x in r})})
'''
CASES['V52b'] = r'''
cov = P.coverage_trace(EXP("f")); cov.__enter__()
cov.run("G", fx.f); types.FunctionType(fx.f.__code__, {})(0)      # one CLONE_CALLED
cov.__exit__(None, None, None); cov.__exit__(None, None, None)    # a second exit
rec = cov.record()
out({"problems": [p.split("]")[0] + "]" for p in rec["problems"]], "score": score("f", rec)})
'''
CASES['V47bc'] = r'''
rfd, wfd = os.pipe()
cov = P.coverage_trace(EXP("f")); cov.__enter__()
def body():
    fx.f()
    pid = os.fork()
    if pid == 0:
        st = P._v5_state()
        r = {"child_before": {"anchors": st["anchors"], "mints": len(st["mints"]), "global_events": st["global_events"]}}
        r["child_anchors_inside_run"] = cov.run("G", lambda: P._v5_state()["anchors"])
        os.write(wfd, json.dumps(r).encode()); os._exit(0)
    os.waitpid(pid, 0)
    return 0
cov.run("G", body); cov.__exit__(None, None, None)
os.close(wfd); data = os.read(rfd, 65536).decode()
out({"child": json.loads(data), "parent": score("f", cov.record())})
'''
CASES['X146e'] = r'''
cov = P.coverage_trace(EXP("f")); cov.__enter__()
held, released = threading.Event(), threading.Event(); T1 = [None]; arm = [True]
def cb(c, off):
    if c is FP["_unwind_on"] and threading.get_ident() == T1[0] and arm[0]:
        arm[0] = False; held.set(); released.wait(10)
M.use_tool_id(3, "p_sm1-hold"); M.register_callback(3, E.PY_START, cb); M.set_local_events(3, FP["_unwind_on"], E.PY_START)
seen = {}
def body():
    st = P._v5_state(); seen["anchors"] = st["anchors"]; seen["global_events"] = st["global_events"]; return 1
def t1():
    T1[0] = threading.get_ident(); cov.run("G", body)
t = threading.Thread(target=t1); t.start(); held.wait(10)
cov.__exit__(None, None, None); released.set(); t.join(10)
M.set_local_events(3, FP["_unwind_on"], 0); M.register_callback(3, E.PY_START, None); M.free_tool_id(3)
out(seen)
'''
CASES['X148b'] = r'''
cov = P.coverage_trace(EXP("f")); cov.__enter__()
held, released, t1done = threading.Event(), threading.Event(), threading.Event(); T1 = [None]; MAIN = threading.get_ident()
arm = {"d": True, "x": True}
def on_call(c, off, callable_, arg0):
    if c is FP["_detach"] and threading.get_ident() == T1[0] and arm["d"] and callable_ is M.get_events:
        arm["d"] = False; held.set(); released.wait(10)
def on_start(c, off):
    if c is FP["_exit_txn"] and threading.get_ident() == MAIN and arm["x"]:
        arm["x"] = False; released.set(); t1done.wait(10)       # X5 waits until T1's close has finished
M.use_tool_id(3, "p_sm1-hold")
M.register_callback(3, E.CALL, on_call); M.register_callback(3, E.PY_START, on_start)
M.set_local_events(3, FP["_detach"], E.CALL); M.set_local_events(3, FP["_exit_txn"], E.PY_START)
def t1():
    T1[0] = threading.get_ident(); cov.run("G", fx.f); t1done.set()
t = threading.Thread(target=t1); t.start(); held.wait(10)
cov.__exit__(None, None, None); t.join(10)
for c in (FP["_detach"], FP["_exit_txn"]): M.set_local_events(3, c, 0)
M.register_callback(3, E.CALL, None); M.register_callback(3, E.PY_START, None); M.free_tool_id(3)
rec = cov.record()
out({"score": score("f", rec), "notes": notes(rec)})
'''
CASES['X153'] = r'''
ident = [None]; results = []
def trial():
    p = P.coverage_trace(EXP("f")); q = P.coverage_trace(EXP("g")); p.__enter__(); q.__enter__()
    release, b_started, a_started = threading.Event(), threading.Event(), threading.Event()
    def bodyA(): fx.f(); a_started.set(); release.wait(10); return 0
    def bodyB(): fx.g(); b_started.set(); release.wait(10); return 0
    t2 = threading.Thread(target=lambda: q.run("G", bodyB))
    def interfere():
        t2.start(); b_started.wait(10)
    st["interfere"] = interfere
    def t1():
        ident[0] = threading.get_ident(); p.run("G", bodyA)
    th = threading.Thread(target=t1); th.start(); a_started.wait(10)
    if not t2.is_alive() and not b_started.is_set():
        t2.start(); b_started.wait(10)
    release.set(); th.join(10); t2.join(10)
    q.__exit__(None, None, None); p.__exit__(None, None, None)
    return [notes(p.record()), notes(q.record())]
st = {}
r = sweep(FP["_unwind_on"], ident, lambda: st["interfere"](), trial, kmax=400)
out({"trials": len(r), "trials_noting_B": sum(1 for a, b in r if b), "trials_noting_A": sum(1 for a, b in r if a)})
'''
CASES['X137k'] = r'''
M.use_tool_id(4, "other")                         # another tool holds id 4, so P takes id 3
p = P.coverage_trace(EXP("f")); p.__enter__(); p.run("G", fx.f)
tool_p = P._v5_state()["tool"]
M.free_tool_id(4)                                 # id 4 is unowned now
arm = [True]
def cb(c, off):
    if c is FP["_ensure_tool"] and arm[0]:
        arm[0] = False; M.free_tool_id(tool_p)     # styxx's id is freed after Q's reconciliation
M.use_tool_id(2, "p_sm1-hold"); M.register_callback(2, E.PY_START, cb); M.set_local_events(2, FP["_ensure_tool"], E.PY_START)
q = P.coverage_trace(EXP("h")); q.__enter__(); tool_q = P._v5_state()["tool"]
M.set_local_events(2, FP["_ensure_tool"], 0); M.register_callback(2, E.PY_START, None); M.free_tool_id(2)
q.run("G", fx.h); q.__exit__(None, None, None); p.__exit__(None, None, None)
out({"tool_at_P": tool_p, "tool_after_Q_enter": tool_q, "P": [score("f", p.record()), notes(p.record())], "Q": [score("h", q.record()), notes(q.record())]})
'''
CASES['V71b'] = r'''
cov = P.coverage_trace(EXP("f")); cov.__enter__()
st = {"k": 0, "n": 0, "in": False, "armed": False, "fired": False}
AUD = ("sys._getframe", "builtins.id", "object.__getattr__")
def hook(ev, args):
    if st["in"] or not st["armed"] or ev not in AUD: return
    st["in"] = True
    try:
        if sys._getframe(1).f_code is FP["_open"]:
            st["n"] += 1
            if st["n"] == st["k"]:
                st["fired"] = True; raise RuntimeError("V71b")
    finally: st["in"] = False
sys.addaudithook(hook)
trials = 0
for k in range(1, 200):
    st.update(k=k, n=0, fired=False, armed=True)
    try: cov.run("G", fx.f)
    except RuntimeError: pass
    st["armed"] = False
    if not st["fired"]: break
    trials += 1
cov.__exit__(None, None, None)
rec = cov.record()
ends = [o["end"] for o in rec["sections"].get("G", [])]
out({"trials": trials, "openings": len(ends), "ends_open": ends.count("open")})
'''
CASES['X132b'] = r'''
ident = [threading.get_ident()]
def kint(): raise KeyboardInterrupt
def trial():
    cov = P.coverage_trace(EXP("f")); cov.__enter__()
    try: cov.run("G", fx.f)
    except KeyboardInterrupt: pass
    cov.__exit__(None, None, None)
    return P._v5_state()["anchors"]               # right after the faulted trace's exit, before any transaction
r = sweep(FP["_open"], ident, kint, trial, kmax=600)
out({"trials": len(r), "trials_with_anchor_left_after_exit": sum(1 for a in r if a)})
'''
CASES['X153b'] = r'''
ident = [threading.get_ident()]; rows = []
def trial():
    p = P.coverage_trace(EXP("f")); q = P.coverage_trace(EXP("g")); q.__enter__(); p.__enter__()
    release, b_started = threading.Event(), threading.Event()
    def bodyB(): fx.g(); b_started.set(); release.wait(10); return 0
    t2 = threading.Thread(target=lambda: q.run("G", bodyB)); t2.start(); b_started.wait(10)
    st["tool"] = P._v5_state()["tool"]
    p.run("G", fx.f)                               # T1 = the case thread; the sweep is over its _unwind_on
    release.set(); t2.join(10); p.__exit__(None, None, None); q.__exit__(None, None, None)
    return ["[V5:MONITOR_LOST]" in notes(q.record()) or "MONITOR_LOST" in str(q.record()["problems"]),
            "[V5:MONITOR_LOST]" in notes(p.record()) or "MONITOR_LOST" in str(p.record()["problems"])]
st = {}
r = sweep(FP["_unwind_on"], ident, lambda: M.set_events(st["tool"], 0), trial, kmax=400)
out({"trials": len(r), "trials_Q_noted": sum(1 for a, b in r if a), "trials_Q_not_noted": [k + 1 for k, (a, b) in enumerate(r) if not a]})
'''
CASES['X156c'] = r'''
import importlib, itertools
P.coverage_trace(EXP("f"))                       # binds
class Chain(itertools.chain): pass
itertools.chain = Chain
P2 = importlib.reload(P)
codes = []
for _ in range(2):
    try: P2.coverage_trace(EXP("f")); codes.append(None)
    except P2.GateSpecError as e: codes.append(code(e))
out({"codes": codes, "MON_survived_reload": P2._MON[0] is not None})
'''
CASES['X37c'] = r'''
real = sys.version_info
class VI(tuple): pass
sys.version_info = VI((real[0], real[1], real[2] + 1, "final", 0))    # the next, unverified patch level
codes = []
for _ in range(2):
    try: P.coverage_trace(EXP("f")); codes.append(None)
    except P.GateSpecError as e: codes.append(code(e))
sys.version_info = real
out({"micro": real[2] + 1, "codes": codes})
'''
CASES['X37b'] = r'''
real = sys.version_info
class VI(tuple): pass
sys.version_info = VI((real[0], real[1], 99, "final", 0))
codes = []
for _ in range(2):
    try: P.coverage_trace(EXP("f")); codes.append(None)
    except P.GateSpecError as e: codes.append(code(e))
sys.version_info = real
out({"codes": codes})
'''
CASES['V52s'] = r'''
res = []
for name in ("P", "Q"):
    cov = P.coverage_trace(EXP("f"))
    cov.__enter__()
    g_in = P._v5_state()["guard"]                  # after the enter's transaction released the mutex
    print(json.dumps({"progress": [name, "guard after enter", g_in]})); sys.stdout.flush()
    cov.run("G", fx.f); cov.__exit__(None, None, None)
    res.append([name, score("f", cov.record()), g_in, P._v5_state()["guard"]])
    print(json.dumps({"progress": res[-1]})); sys.stdout.flush()
out({"traces": res})
'''
BOUND = {'V52s': 30}
PLAN = [('X26g', ['spec', 'A_coh_no_file_skip']), ('X24g', ['spec', 'A_cache_callee_identity']),
        ('V07b', ['spec', 'A_alias_by_name']), ('V74', ['spec', 'A_mint_eq']), ('V36c', ['spec', 'A_visible_deleted']),
        ('X71d', ['spec', 'A_publish_recheck']), ('X32e', ['spec', 'A_enter_claim']),
        ('V52b', ['spec', 'A_exit_claim', 'M5_exit_claim_not_idempotent']),
        ('V47bc', ['spec', 'A_atfork_handler', 'A_pid_passthrough']), ('X146e', ['spec', 'A_unwind_on_recheck']),
        ('X148b', ['spec', 'A_detach_anchor_first']), ('X153', ['spec', 'A_capture_outside', 'R13_capture_stale_read']), ('X153b', ['spec', 'A_capture_outside', 'R13_capture_stale_read']),
        ('X137k', ['spec', 'A_ensure_no_reclaim']), ('V71b', ['spec', 'A_open_audited_after_append']),
        ('X132b', ['spec', 'M3_register_before_append']),
        ('X156c', ['spec', 'A_binding_first_only']), ('X37b', ['spec', 'A_verified_widened']),
        ('X37c', ['spec', 'A_verified_widened']),
        ('V52s', ['spec', 'R13_total_walk', 'A_txn_shared_succ', 'A_txn_shared_succ+R13_total_walk'])]
def prereg(path, targets):
    spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.0, "exercises": ["fx_r13:" + t for t in targets]}},
            "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {"G": False}, "verdict": "FAIL"}], "smoke_verdict": "INVALID__s"}
    open(path, 'w').write('# r13\n\n```gates\n%s\n```\n' % json.dumps(spec))
def main():
    src = open(REF, encoding='utf-8').read()
    print(sys.version.split()[0], 'ref_v5f.py sha256', hashlib.sha256(src.encode()).hexdigest()[:16], flush=True)
    work = tempfile.mkdtemp(prefix='r13_'); os.makedirs(os.path.join(work, 'fx')); repo = os.path.join(work, 'repo'); os.makedirs(repo)
    open(os.path.join(work, 'fx', 'fx_r13.py'), 'w').write(FIX)
    for name, ts in (('f', ['f']), ('g', ['g']), ('h', ['h']), ('fg', ['f', 'g']), ('blk', ['blk']), ('wrapped_g', ['wrapped_g']),
                     ('power2', ['power2']), ('cached', ['cached'])):
        prereg(os.path.join(repo, 'PREREG_%s.md' % name), ts)
    git = ['git', '-c', 'user.name=r13', '-c', 'user.email=r13@invalid', '-c', 'commit.gpgsign=false']
    subprocess.run(['git', 'init', '-q'], cwd=repo, check=True); subprocess.run(git + ['add', '.'], cwd=repo, check=True)
    subprocess.run(git + ['commit', '-q', '-m', 'p'], cwd=repo, check=True)
    only = sys.argv[1:]
    for case, variants in PLAN:
        if only and case not in only: continue
        for v in variants:
            s = src
            for part in v.split('+'):
                for old, new in MUT[part]:
                    assert s.count(old) == 1, (v, old[:60], s.count(old)); s = s.replace(old, new)
            os.makedirs(os.path.join(work, v), exist_ok=True)
            path = os.path.join(work, v, 'ref_v5f.py'); open(path, 'w').write(s)
            prog = os.path.join(work, 'case_%s.py' % case); open(prog, 'w').write(SETUP + CASES[case])
            try:
                r = subprocess.run([sys.executable, prog, work, path], capture_output=True, text=True, timeout=BOUND.get(case, 600))
                res = r.stdout.strip() or ('ERROR ' + (r.stderr.strip().splitlines() or ['?'])[-1])
            except subprocess.TimeoutExpired as e:
                got = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or '')
                res = 'TIMEOUT (%d s) after: %s' % (BOUND.get(case, 600), got.strip().replace(chr(10), ' | ') or '(nothing)')
            print('%-6s %-30s %s' % (case, v, res), flush=True)
main()
