# rev11: witnesses for the exam author's revision-10 follow-ups (GAP-33, GAP-34, GAP-36) and the probe behind the
# GAP-36 correction of M3's leftover-events sentence. Same method as rev10/p_rev10.py: a snapshot of
# v5f_exam/ref_v5f.py, single-rule mutants by exact replacement in memory, one fresh subprocess per (case, variant).
#   V72b  GAP-33: a dead exiting token: record() refuses TRACE_INCOMPLETE, still, after a later trace pruned the core
#   X35e  GAP-34: an aiodebug-shaped closure bound as Handle._run: every coverage_trace() refuses while it is bound
#   X57d  GAP-36 W066: over-blocking #19 pinned: a joined mint's freeze0 predates the trace (CLONE_ALIVE in the joiner)
#   R23   GAP-36 W074: L-CLONE's swap-and-restore door pinned (PASS, credited)
#   R24   GAP-36 W076: L-CLONE's frozen-clone door pinned (the freeze count does not rise; PASS, credited)
#   X117g GAP-36 W224: check_metrics runs a metric's __float__ override exactly once, and no __bool__
#   J225  GAP-36 W225 (C): json.loads gives exact-str keys
#   X137j GAP-36 W141: what a foreign tool leaves on a freed id after styxx reclaims it
# Run: <venv3.12|venv3.13>/bin/python p_rev11.py
import hashlib, json, os, subprocess, sys, tempfile
REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'v5f_exam', 'ref_v5f.py')
MUTANTS = {
    'spec': [],
    'mut_prune_marks_exited': [('def _prune(h):\n    for o in list(h.openings):\n',
                                "def _prune(h):\n    h.marks['exited'] = True\n    for o in list(h.openings):\n")],
    'mut_no_locals_clause': [("if '<locals>' in c.co_qualname or twins:", "if twins:")],
    'mut_cut_before_scan': [('        twins = [r for r', '        _CUT.setdefault(id(c), c)\n        twins = [r for r')],
    'mut_freeze0_at_join': [('        m.holders = m.holders + (core,)\n', '        m.holders = m.holders + (core,)\n        m.freeze0 = gc.get_freeze_count()\n')],
    'mut_freeze_ne': [('if gc.get_freeze_count() > m.freeze0:', 'if gc.get_freeze_count() != m.freeze0:')],
    'mut_cm_bool': [('usable = issubclass(tv, (int, float)) and tv is not bool and _finite(val)',
                     'usable = issubclass(tv, (int, float)) and tv is not bool and _finite(val) and (bool(val) or True)')],
}
FIX = {'fx_r11.py': '''
import asyncio.events, threading
def f(x=0): return x + 1
def u(x=0): return x + 100
def enable():                                   # aiodebug 2.3.0's log_slow_callbacks.enable() shape
    orig = asyncio.events.Handle._run
    def instrumented(self):
        return orig(self)
    asyncio.events.Handle._run = instrumented
    return orig
'''}
SETUP = r'''
import sys, os, json, threading, gc, types, importlib.util
WORK, SRC = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("ref_v5f", SRC)
P = importlib.util.module_from_spec(spec); sys.modules["ref_v5f"] = P; spec.loader.exec_module(P)
sys.path.insert(0, os.path.join(WORK, "fx"))
import fx_r11
def EXP(k="F"): return P.Experiment(os.path.join(WORK, "repo", "PREREG_%s.md" % k))
def code(e):
    s = str(e); return s[s.index("[V5:")+4:s.index("]")] if "[V5:" in s else type(e).__name__
def rec_or(cov):
    try: return cov.record()
    except P.GateSpecError as e: return code(e)
def score(rec):
    try: v = EXP().score({"m": 1.0, "coverage_trace": rec}); return ["PASS", v.coverage]
    except P.GateSpecError as e: return ["REFUSE", code(e)]
'''
CASES = {
 'V72b': r'''
armed = {"on": False}
def hook(ev, a):
    if armed["on"] and ev == "sys.monitoring.register_callback":
        armed["on"] = False; raise RuntimeError("V72")
sys.addaudithook(hook)
cov = P.coverage_trace(EXP()); cov.__enter__(); cov.run("G", fx_r11.f)
armed["on"] = True
try: cov.__exit__(None, None, None)
except RuntimeError: pass
first = rec_or(cov)
with P.coverage_trace(EXP()) as cov2: cov2.run("G", fx_r11.f)
second = rec_or(cov)
print(json.dumps({"record_before": first, "record_after_next_trace": second if isinstance(second, str) else "a record"}))
''',
 'X35e': r'''
import asyncio.events as ev
out = []
orig = fx_r11.enable()
try:
    for _ in range(2):
        try: P.coverage_trace(EXP()); out.append("constructed")
        except P.GateSpecError as e: out.append(code(e))
finally:
    ev.Handle._run = orig
try: P.coverage_trace(EXP()); out.append("constructed")
except P.GateSpecError as e: out.append(code(e))
print(json.dumps(out))
''',
}
CASES['X57d'] = r'''
go, inside = threading.Event(), threading.Event()
cov_p = P.coverage_trace(EXP("B")); cov_p.__enter__()            # P mints blk: freeze0 = the count now
junk = [[i] for i in range(2000)]; gc.freeze()                    # the count rises after the mint
cov_q = P.coverage_trace(EXP("B")); cov_q.__enter__()            # Q joins P's mint
t = threading.Thread(target=fx_r11b.blk, args=(inside, go)); t.start(); inside.wait(10)   # M_T executing
cov_q.__exit__(None, None, None)
go.set(); t.join(10)
cov_p.__exit__(None, None, None)
gc.unfreeze()
q = rec_or(cov_q); p = rec_or(cov_p)
print(json.dumps({"Q_problems": [x.split("]")[0] + "]" for x in q["problems"]], "P_problems": [x.split("]")[0] + "]" for x in p["problems"]]}))
'''
CASES['R23'] = r'''
u0 = fx_r11.u.__code__
with P.coverage_trace(EXP()) as cov:
    def sec():
        fx_r11.f(); fx_r11.u.__code__ = fx_r11.f.__code__; fx_r11.u(); fx_r11.u.__code__ = u0
    cov.run("G", sec)
r = rec_or(cov)
print(json.dumps({"score": score(r), "problems": r["problems"]}))
'''
CASES['R24'] = r'''
big = [[i] for i in range(300000)]; gc.freeze(); n0 = gc.get_freeze_count()
with P.coverage_trace(EXP()) as cov:
    def sec():
        global clone
        clone = types.FunctionType(fx_r11.f.__code__, fx_r11.f.__globals__); clone(1)
        gc.unfreeze(); big.clear(); gc.collect(); gc.freeze()
    cov.run("G", sec)
    n1 = gc.get_freeze_count()
gc.unfreeze(); r = rec_or(cov)
print(json.dumps({"count_not_risen": n1 <= n0, "score": score(r), "problems": [x.split("]")[0] + "]" for x in r["problems"]]}))
'''
CASES['X117g'] = r'''
cnt = {"float": 0, "bool": 0}
class I(int):
    def __float__(s): cnt["float"] += 1; return int.__float__(s)
    def __bool__(s): cnt["bool"] += 1; return True
m = EXP().check_metrics({"m": I(3)})["G"]
print(json.dumps({"usable": m["usable"], "calls": cnt}))
'''
CASES['J225'] = r'''
d = json.loads('{"a": {"b": 1}, "c": [ {"d": 2} ]}')
ks = list(d) + list(d["a"]) + list(d["c"][0])
print(json.dumps({"all_exact_str": all(type(k) is str for k in ks)}))
'''
CASES['X137j'] = r'''
M = sys.monitoring
cov = P.coverage_trace(EXP()); cov.__enter__(); cov.run("G", fx_r11.f); cov.__exit__(None, None, None)
t = P._v5_state()["tool"]
def foreign_line(*a): return None
def foreign_entry(*a): return None
M.free_tool_id(t)
M.use_tool_id(t, "other")
M.register_callback(t, M.events.LINE, foreign_line)            # an event styxx never registers
M.register_callback(t, M.events.PY_START, foreign_entry)       # an event styxx registers
M.set_events(t, M.events.LINE)
M.set_local_events(t, fx_r11.u.__code__, M.events.PY_START)
M.free_tool_id(t)                                              # left behind: callbacks and events
with P.coverage_trace(EXP()) as cov2: cov2.run("G", fx_r11.f)  # the next transaction reclaims t
out = {"tool_ours": P._v5_state()["tool_ours"], "global_events": M.get_events(t),
       "local_events_u": M.get_local_events(t, fx_r11.u.__code__)}
prev = M.register_callback(t, M.events.LINE, None); out["line_callback_is_foreign"] = prev is foreign_line
M.register_callback(t, M.events.LINE, prev)
prev = M.register_callback(t, M.events.PY_START, None); out["py_start_callback_is_foreign"] = prev is foreign_entry
M.register_callback(t, M.events.PY_START, prev)
M.set_local_events(t, fx_r11.u.__code__, 0); M.register_callback(t, M.events.LINE, None)
print(json.dumps(out))
'''
FIX['fx_r11b.py'] = 'def blk(inside, go):\n    inside.set(); go.wait(10); return 0\n'
PLAN = [('V72b', ['spec', 'mut_prune_marks_exited']),
        ('X35e', ['spec', 'mut_no_locals_clause', 'mut_cut_before_scan']),
        ('X57d', ['spec', 'mut_freeze0_at_join']),
        ('R23', ['spec']),
        ('R24', ['spec', 'mut_freeze_ne']),
        ('X117g', ['spec', 'mut_cm_bool']),
        ('J225', ['spec']),
        ('X137j', ['spec'])]

def prereg(path, gates):
    spec = {"gates": gates, "outcomes": [{"when": {k: True for k in gates}, "verdict": "PASS"}]
            + [{"when": {k: False}, "verdict": "FAIL_" + k} for k in gates], "smoke_verdict": "INVALID__smoke"}
    open(path, 'w').write('# r11\n\n```gates\n%s\n```\n' % json.dumps(spec, indent=1))

def main():
    src = open(REF, encoding='utf-8').read()
    print(sys.version.split()[0], 'ref_v5f.py sha256', hashlib.sha256(src.encode()).hexdigest()[:16])
    work = tempfile.mkdtemp(prefix='r11_')
    os.makedirs(os.path.join(work, 'fx')); repo = os.path.join(work, 'repo'); os.makedirs(repo)
    for n, t in FIX.items(): open(os.path.join(work, 'fx', n), 'w').write(t)
    prereg(os.path.join(repo, 'PREREG_F.md'), {"G": {"metric": "m", "op": ">=", "value": 0.0, "exercises": ["fx_r11:f"]}})
    prereg(os.path.join(repo, 'PREREG_B.md'), {"G": {"metric": "m", "op": ">=", "value": 0.0, "exercises": ["fx_r11b:blk"]}})
    git = ['git', '-c', 'user.name=r11', '-c', 'user.email=r11@invalid', '-c', 'commit.gpgsign=false']
    subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
    subprocess.run(git + ['add', '.'], cwd=repo, check=True)
    subprocess.run(git + ['commit', '-q', '-m', 'p'], cwd=repo, check=True)
    for case, variants in PLAN:
        for v in variants:
            s = src
            for old, new in MUTANTS[v]:
                assert s.count(old) == 1, (v, old, s.count(old)); s = s.replace(old, new)
            path = os.path.join(work, 'ref_%s.py' % v); open(path, 'w', encoding='utf-8').write(s)
            prog = os.path.join(work, 'case_%s.py' % case); open(prog, 'w').write(SETUP + "import fx_r11b\n" + CASES[case])
            r = subprocess.run([sys.executable, prog, work, path], capture_output=True, text=True, timeout=180)
            res = r.stdout.strip() or ('ERROR ' + (r.stderr.strip().splitlines() or ['?'])[-1])
            print('%-6s %-24s %s' % (case, v, res))
main()
