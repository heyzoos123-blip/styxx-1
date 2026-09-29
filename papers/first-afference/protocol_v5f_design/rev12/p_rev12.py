# rev12: witnesses for the exam author's revision-11 follow-ups, on v5f_exam/ref_v5f.py (read only) and on
# single-rule mutants built in memory; one fresh subprocess per (case, variant).
#   X137h  GAP-42: P, Q and S each open their gate's section once (calling nothing), so each refuses NOT_EXERCISED
#   X154d  GAP-41: variant (b), the hook acting at the 1st register_callback event only
#   X38    GAP-38: the 3.12.3 freeze-count rise after gc.unfreeze() (no gc.freeze()), with M_T in an untracked tuple
# Run: <venv3.12|venv3.13>/bin/python p_rev12.py
import hashlib, json, os, subprocess, sys, tempfile
REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'v5f_exam', 'ref_v5f.py')
MUTANTS = {
 'spec': [],
 'mut_rebind_nocount': [('                if _TOOL[0] is not None:             # a rebinding or a re-take: counted (rev. 6, 7)\n                    _LOST.append(True)\n',
                         '                if _TOOL[0] is not None:             # a rebinding or a re-take: counted (rev. 6, 7)\n                    pass\n')],
}
SETUP = r'''
import sys, os, json, gc, threading, importlib.util
WORK, SRC = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("ref_v5f", SRC)
P = importlib.util.module_from_spec(spec); sys.modules["ref_v5f"] = P; spec.loader.exec_module(P)
sys.path.insert(0, os.path.join(WORK, "fx")); import fx_r12
M = sys.monitoring; E = M.events
def EXP(k): return P.Experiment(os.path.join(WORK, "repo", "PREREG_%s.md" % k))
def code(e):
    s = str(e); return s[s.index("[V5:")+4:s.index("]")] if "[V5:" in s else type(e).__name__
def outcome(k, cov):
    rec = cov.record()
    notes = sorted({n.split("]")[0] + "]" for ops in rec["sections"].values() for o in ops for n in o["notes"]})
    try: EXP(k).score({"m": 1.0, "coverage_trace": rec}); c = "PASS"
    except P.GateSpecError as e: c = code(e)
    return [c, notes]
def noop(): return None
'''
CASES = {
 'X137h': r'''
p = P.coverage_trace(EXP("g")); p.__enter__(); p.run("G", noop)          # P on g, id 4; its section calls nothing
M.free_tool_id(4); M.use_tool_id(4, "U"); M.register_callback(4, E.RAISE, lambda *a: None)   # U: styxx's callbacks stay
q = P.coverage_trace(EXP("h")); q.__enter__(); q.run("G", noop)          # Q rebinds to id 3
r = P.coverage_trace(EXP("t")); r.__enter__()
def sec_a():
    M.free_tool_id(3); M.use_tool_id(3, "V")
    for ev in (E.PY_START, E.PY_RESUME, E.PY_RETURN, E.PY_YIELD, E.PY_UNWIND):
        M.register_callback(3, ev, lambda *a: None)                         # PY_UNWIND left set
    try: fx_r12.t()
    except ValueError: pass
r.run("G", sec_a)
M.register_callback(4, E.RAISE, None); M.free_tool_id(4)                 # U leaves id 4
s = P.coverage_trace(EXP("g")); s.__enter__(); tool = P._v5_state()["tool"]; s.run("G", noop)   # S rebinds to id 4
for c in (s, q, r, p): c.__exit__(None, None, None)
print(json.dumps({"tool_after_S_enter": tool, "P": outcome("g", p), "Q": outcome("h", q), "R": outcome("t", r), "S": outcome("g", s)}))
''',
 'X154d_b': r'''
p = P.coverage_trace(EXP("f")); p.__enter__(); p.run("G", fx_r12.f)
t0 = P._v5_state()["tool"]; M.free_tool_id(t0)                           # an outside party frees styxx's id
st = {"n": 0}
def hook(ev, a):
    if ev == "sys.monitoring.register_callback" and threading.current_thread() is threading.main_thread():
        st["n"] += 1
        if st["n"] == 1:                                                  # variant (b): the 1st event only
            def other():
                M.free_tool_id(t0); M.use_tool_id(t0, "other")
            th = threading.Thread(target=other); th.start(); th.join()
sys.addaudithook(hook)
q = P.coverage_trace(EXP("g")); q.__enter__(); tool = P._v5_state()["tool"]; q.run("G", fx_r12.g)
q.__exit__(None, None, None); p.__exit__(None, None, None)
print(json.dumps({"tool_after_Q_enter": tool, "P": outcome("f", p), "Q": outcome("g", q)}))
''',
 'X38': r'''
out = {}
for unfrozen in (False, True):
    if unfrozen: gc.unfreeze()
    keep = []
    with P.coverage_trace(EXP("f")) as cov:
        cov.run("G", fx_r12.f)
        keep.append((fx_r12.f.__code__,))       # M_T held by a tuple gc does not track
        gc.collect()
    out["after_unfreeze" if unfrozen else "fresh_process"] = outcome("f", cov)
    keep.clear(); gc.collect()
gc.unfreeze(); gc.collect()                    # revision 12's hygiene: unfreeze, then a full collection
keep = []
with P.coverage_trace(EXP("f")) as cov:
    cov.run("G", fx_r12.f); keep.append((fx_r12.f.__code__,)); gc.collect()
out["after_unfreeze_then_collect"] = outcome("f", cov)
print(json.dumps(out))
''',
}
FIX = 'def f(x=0): return x + 1\ndef g(x=0): return x + 2\ndef h(x=0): return x + 3\ndef t():\n    raise ValueError("t")\n'
PLAN = [('X137h', ['spec', 'mut_rebind_nocount']), ('X154d_b', ['spec']), ('X38', ['spec'])]
def prereg(path, target):
    spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.0, "exercises": ["fx_r12:" + target]}},
            "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {"G": False}, "verdict": "FAIL"}], "smoke_verdict": "INVALID__s"}
    open(path, 'w').write('# r12\n\n```gates\n%s\n```\n' % json.dumps(spec))
def main():
    src = open(REF, encoding='utf-8').read()
    print(sys.version.split()[0], 'ref_v5f.py sha256', hashlib.sha256(src.encode()).hexdigest()[:16])
    work = tempfile.mkdtemp(prefix='r12_'); os.makedirs(os.path.join(work, 'fx')); repo = os.path.join(work, 'repo'); os.makedirs(repo)
    open(os.path.join(work, 'fx', 'fx_r12.py'), 'w').write(FIX)
    for k in 'fght': prereg(os.path.join(repo, 'PREREG_%s.md' % k), k)
    git = ['git', '-c', 'user.name=r12', '-c', 'user.email=r12@invalid', '-c', 'commit.gpgsign=false']
    subprocess.run(['git', 'init', '-q'], cwd=repo, check=True); subprocess.run(git + ['add', '.'], cwd=repo, check=True)
    subprocess.run(git + ['commit', '-q', '-m', 'p'], cwd=repo, check=True)
    for case, variants in PLAN:
        for v in variants:
            s = src
            for old, new in MUTANTS[v]:
                assert s.count(old) == 1, (v, old[:50]); s = s.replace(old, new)
            path = os.path.join(work, 'ref_%s.py' % v); open(path, 'w').write(s)
            prog = os.path.join(work, 'case_%s.py' % case); open(prog, 'w').write(SETUP + CASES[case])
            r = subprocess.run([sys.executable, prog, work, path], capture_output=True, text=True, timeout=300)
            print('%-8s %-20s %s' % (case, v, r.stdout.strip() or ('ERROR ' + (r.stderr.strip().splitlines() or ['?'])[-1])))
main()
