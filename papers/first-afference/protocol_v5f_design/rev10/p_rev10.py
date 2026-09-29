# rev10: witnesses for the verifier's findings on revision 9 (R9-1..R9-9), each run on a snapshot of
# v5f_exam/ref_v5f.py (the reference after revision 9; revision 10 changes no mechanism, so the patched copy
# is the reference itself) and on single-rule mutants built by exact string replacement in memory. One fresh
# subprocess per (case, variant). Nothing under v5f_exam/ is written.
# Run: <venv3.12|venv3.13>/bin/python p_rev10.py
import hashlib, json, os, subprocess, sys, tempfile

REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'v5f_exam', 'ref_v5f.py')

WALK = '''                if not issubclass(type(val), dict):
                    found = False
                    break
                val = dict.get(val, k, _MISSING)
'''
MUTANTS = {
    'spec': [],
    # R9-1: rendering a non-str section or a type name
    'mut_sec_repr': [('f"{_TYPE_QUAL.__get__(type(section))} is not a str;', 'f"{section!r} is not a str;')],
    'mut_sec_attrqual': [('f"{_TYPE_QUAL.__get__(type(section))} is not a str;', 'f"{type(section).__qualname__} is not a str;')],
    'mut_inactive_repr': [('shown = repr(section) if type(section) is str else "of type " + _TYPE_QUAL.__get__(type(section))',
                           'shown = repr(section)')],
    'mut_inactive_attrqual': [('shown = repr(section) if type(section) is str else "of type " + _TYPE_QUAL.__get__(type(section))',
                               'shown = repr(section) if type(section) is str else "of type " + type(section).__qualname__')],
    'mut_notrace1_attrqual': [('f"{_TYPE_QUAL.__get__(type(result))}, not a dict', 'f"{type(result).__qualname__}, not a dict')],
    'mut_notrace3_attrqual': [('is a {_TYPE_QUAL.__get__(type(tr))}, ', 'is a {type(tr).__qualname__}, ')],
    'mut_stamp_attrqual': [('(a {_TYPE_QUAL.__get__(type(stamped))})', '(a {type(stamped).__qualname__})')],
    # R9-9
    'mut_callee_none_text': [('cname = "no single Python function"', 'cname = repr(callee)')],
    # R9-2: the NESTED walk mirrors M6 (stops at a foreign-loop anchor)
    'mut_nested_mirror': [('        p = _ANCHORS.get(g)\n        if p is not None and p.core is core and p.loop is loop:\n',
                           '        p = _ANCHORS.get(g)\n        if p is not None and p.loop is not loop:\n            break\n'
                           '        if p is not None and p.core is core and p.loop is loop:\n')],
    # R9-3, R9-4 (the verifier's mutants)
    'mut_grl_check_once': [
        ('    if not (type(grl) is BuiltinFunctionType and grl.__name__ == "_get_running_loop"\n',
         '    if g.get("_get_running_loop") is None and not (type(grl) is BuiltinFunctionType and grl.__name__ == "_get_running_loop"\n'),
        ('    _get_running_loop = grl\n', '    if _get_running_loop is None:\n        _get_running_loop = grl\n')],
    'mut_bind_before_asyncio': [('    import asyncio                                   # M0 step 5 (GAP-09)\n',
                                 '    if _MON[0] is None:\n        _MON[0] = mon\n    import asyncio\n')],
    # R9-5: check_metrics' walk and its smoke note (first occurrence of the walk: the metric paths)
    'mut_cm_resolve': [(WALK, '''                if not isinstance(val, dict) or k not in val:
                    found = False
                    break
                val = val[k]
''', 1)],
    'mut_cm_get': [(WALK, '''                if not issubclass(type(val), dict):
                    found = False
                    break
                val = val.get(k, _MISSING)
''', 1)],
    'mut_cm_smoke': [('                if smoke and not present:\n', '                if not present:\n')],
    # R9-8: the guard field
    'mut_guard_no_alive': [('("held" if _alive(r) else "dead")', '"held"')],
    'mut_guard_never_held': [('("held" if _alive(r) else "dead")', '"dead"')],
}

FIX = r'''
import functools
CNT = {"qual": 0, "repr": 0}
class CountMeta(type):
    def __getattribute__(cls, n):
        if n in ("__qualname__", "__name__"): CNT["qual"] += 1
        return type.__getattribute__(cls, n)
class Stamp(metaclass=CountMeta):
    def __repr__(s): CNT["repr"] += 1; return "Stamp()"
def f(x=0): return x + 1
def g(x=0): return x + 2
cached_len = functools.lru_cache(None)(len)              # X24f: a cache wrapper over a non-function
def _body(x): return x
stamped_w = functools.lru_cache(None)(_body)             # X24f variant: its __wrapped__ is a Stamp()
stamped_w.__wrapped__ = Stamp()
del _body
'''

SETUP = r'''
import sys, os, json, types, subprocess, importlib.util, asyncio
WORK, SRC = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("ref_v5f", SRC)
P = importlib.util.module_from_spec(spec); sys.modules["ref_v5f"] = P; spec.loader.exec_module(P)
sys.path.insert(0, os.path.join(WORK, "fx"))
import fx_r10
def EXP(k): return P.Experiment(os.path.join(WORK, "repo", "PREREG_%s.md" % k))
def code(e):
    s = str(e); return s[s.index("[V5:")+4:s.index("]")] if "[V5:" in s else type(e).__name__
def score(exp, rec):
    try: v = exp.score({"m": 1.0, "coverage_trace": rec}); return ["PASS", v.coverage]
    except P.GateSpecError as e: return ["REFUSE", code(e)]
class CountMeta(type):
    n = {"qual": 0}
    def __getattribute__(cls, a):
        if a in ("__qualname__", "__name__"): CountMeta.n["qual"] += 1
        return type.__getattribute__(cls, a)
class Sec(metaclass=CountMeta):
    c = {"eq": 0, "hash": 0, "repr": 0, "str": 0, "format": 0}
    def __eq__(s, o): Sec.c["eq"] += 1; return False
    def __hash__(s): Sec.c["hash"] += 1; return 0
    def __repr__(s): Sec.c["repr"] += 1; return "Sec()"
    def __str__(s): Sec.c["str"] += 1; return "Sec"
    def __format__(s, spec): Sec.c["format"] += 1; return "Sec"
def counters(): return dict(Sec.c, meta_qual=CountMeta.n["qual"])
'''

CASES = {
 # R9-1, step 3: X78f's variant extended to __repr__/__str__/__format__ and a metaclass __qualname__/__name__ read
 'X78f_ext': r'''
with P.coverage_trace(EXP("F")) as cov:
    try: cov.run(Sec(), fx_r10.f); r = "no refusal"
    except P.GateSpecError as e: r = code(e)
    cov.run("G", fx_r10.f)
print(json.dumps({"refusal": r, "counters": counters()}))
''',
 # R9-1, step 2: a non-str section refused TRACE_INACTIVE, before enter and after exit
 'X78h': r'''
cov = P.coverage_trace(EXP("F")); out = {}
try: cov.run(Sec(), fx_r10.f); out["before_enter"] = "no refusal"
except P.GateSpecError as e: out["before_enter"] = code(e)
cov2 = P.coverage_trace(EXP("F"))
with cov2: cov2.run("G", fx_r10.f)
try: cov2.run(Sec(), fx_r10.f); out["after_exit"] = "no refusal"
except P.GateSpecError as e: out["after_exit"] = code(e)
out["counters"] = counters()
print(json.dumps(out))
''',
 # R9-1, NO_TRACE texts: type names read through the C descriptor
 'X93e': r'''
class R(metaclass=CountMeta): pass
class MD(dict, metaclass=CountMeta): pass
exp = EXP("F")
n1 = exp.check_metrics(R())["G:exercises"]["note"]
tr = MD(tracer="styxx.protocol.coverage_trace/3")
try: exp.score({"m": 1.0, "coverage_trace": tr}); n3 = "no refusal"
except P.GateSpecError as e: n3 = str(e)
print(json.dumps({"first": n1[n1.index("the result"):n1.index(", not a dict") + 12],
                  "third": n3[n3.index("'coverage_trace' is"):], "meta_qual": CountMeta.n["qual"]}))
''',
 # R9-1 / R9-9: cache wrappers whose callee is not a single function, or whose stamp has a counting metaclass
 'X24f': r'''
out = {}
for k in ("L", "S"):
    try:
        with P.coverage_trace(EXP(k)) as cov: pass
        out[k] = "no refusal"
    except P.GateSpecError as e:
        s = str(e); out[k] = [code(e), s[s.index("the wrapper calls"):s.index("; declare")]]
out["fixture_counters"] = fx_r10.CNT
print(json.dumps(out))
''',
 # R9-2: over-block #23 pinned (the verifier's FB shape)
 'X84': r'''
from asyncio import events
L1 = asyncio.new_event_loop(); out = {}
with P.coverage_trace(EXP("F")) as cov, P.coverage_trace(EXP("F")) as cov2:
    def inner_same_core():
        events._set_running_loop(L1)
        try:
            try: cov.run("G", fx_r10.f); out["open_Q"] = "opened"
            except P.GateSpecError as e: out["open_Q"] = code(e)
        finally:
            events._set_running_loop(None)
    def middle_other_tracer():
        events._set_running_loop(None)
        cov2.run("G", inner_same_core)
        events._set_running_loop(L1)
    events._set_running_loop(L1)
    try: cov.run("G", middle_other_tracer)
    finally: events._set_running_loop(None)
out["problems"] = [p.split("]")[0] + "]" for p in cov.record()["problems"]]
L1.close()
print(json.dumps(out))
''',
 # R9-3: _get_running_loop replaced after the first trace
 'X156h': r'''
import asyncio.events as ev
with P.coverage_trace(EXP("F")) as cov: cov.run("G", fx_r10.f)
first = score(EXP("F"), cov.record())
orig = ev._get_running_loop; ev._get_running_loop = lambda: None
try:
    try:
        with P.coverage_trace(EXP("F")) as cov2: cov2.run("G", fx_r10.f)
        second = score(EXP("F"), cov2.record())
    except P.GateSpecError as e: second = ["RAISE", code(e)]
finally:
    ev._get_running_loop = orig
print(json.dumps({"first": first, "second": second}))
''',
 # R9-4: a refusal at step 6 binds nothing (the verifier's FC shape)
 'X156i': r'''
import asyncio.events as ev
orig = ev._get_running_loop; ev._get_running_loop = lambda: None
try:
    try: P.coverage_trace(EXP("F")); a = "constructed"
    except P.GateSpecError as e: a = code(e)
finally:
    ev._get_running_loop = orig
st = P._v5_state()
sm = sys.monitoring; orig_se = sm.set_events
sm.set_events = lambda *x: orig_se(*x)
try:
    try:
        with P.coverage_trace(EXP("F")) as cov: cov.run("G", fx_r10.f)
        b = score(EXP("F"), cov.record())
    except P.GateSpecError as e: b = ["RAISE", code(e)]
finally:
    sm.set_events = orig_se
print(json.dumps({"first": a, "state_after_refusal": {k: st[k] for k in ("tool", "tool_ours", "cut", "cut_current")}, "second_with_wrapper": b}))
''',
 # R9-5: check_metrics through dict subclasses with user methods; the non-smoke absent-trace note
 'X117e': r'''
cnt = {"n": 0}
class UD(dict):
    def __getitem__(s, k): cnt["n"] += 1; return dict.__getitem__(s, k)
    def __contains__(s, k): cnt["n"] += 1; return dict.__contains__(s, k)
    def get(s, k, d=None): cnt["n"] += 1; return dict.get(s, k, d)
    def __missing__(s, k): cnt["n"] += 1; return 1.0
    def __bool__(s): cnt["n"] += 1; return True
    def keys(s): cnt["n"] += 1; return dict.keys(s)
    def __iter__(s): cnt["n"] += 1; return dict.__iter__(s)
exp = EXP("N")
r_ok = UD(a=UD(b=0.5))
r_missing = UD(a=UD())
m1 = exp.check_metrics(r_ok)["G"]
m2 = exp.check_metrics(r_missing)["G"]
print(json.dumps({"present_usable": [m1["present"], m1["usable"]], "missing": [m2["present"], m2["usable"]], "user_calls": cnt["n"]}))
''',
 'X117f': r'''
exp = EXP("F")
n_off = exp.check_metrics({"m": 1.0})["G:exercises"]["note"]
n_on = exp.check_metrics({"m": 1.0, "smoke": True})["G:exercises"]["note"]
print(json.dumps({"smoke_off": n_off[:14] + "|" + ("the result has no 'coverage_trace' key" in n_off and "2nd wording" or "?"), "smoke_on": n_on}))
''',
 # R9-8: guard "held" inside the exit transaction, "dead" after it raised, "free" after the next trace
 'V72': r'''
seen = {}; armed = {"on": False}
def hook(ev, args):
    if armed["on"] and ev == "sys.monitoring.register_callback":
        armed["on"] = False
        seen["inside"] = P._v5_state()["guard"]
        raise RuntimeError("V72")
sys.addaudithook(hook)
cov = P.coverage_trace(EXP("F"))
cov.__enter__(); cov.run("G", fx_r10.f)
armed["on"] = True
try: cov.__exit__(None, None, None); seen["exit"] = "returned"
except RuntimeError: seen["exit"] = "RuntimeError"
seen["after"] = P._v5_state()["guard"]
with P.coverage_trace(EXP("F")) as cov2: cov2.run("G", fx_r10.f)
seen["next"] = score(EXP("F"), cov2.record())
seen["end"] = P._v5_state()["guard"]
print(json.dumps(seen))
''',
 # R9-6: the leftover rule in a fresh process whose case makes the first tracer
 'LEFTOVER': r'''
before = P._v5_state()
with P.coverage_trace(EXP("F")) as cov: cov.run("G", fx_r10.f)
after = P._v5_state()
differ = sorted(k for k in before if before[k] != after[k])
old_rule = [k for k in differ if k not in ("cut", "tool")]
new_rule = [k for k in differ if k not in ("cut", "tool") and not (k == "tool_ours" and before["tool"] is None)]
print(json.dumps({"differ": differ, "violations_rev9_rule": old_rule, "violations_rev10_rule": new_rule}))
''',
}

PLAN = [('X78f_ext', ['spec', 'mut_sec_repr', 'mut_sec_attrqual']),
        ('X78h', ['spec', 'mut_inactive_repr', 'mut_inactive_attrqual']),
        ('X93e', ['spec', 'mut_notrace1_attrqual', 'mut_notrace3_attrqual']),
        ('X24f', ['spec', 'mut_stamp_attrqual', 'mut_callee_none_text']),
        ('X84', ['spec', 'mut_nested_mirror']),
        ('X156h', ['spec', 'mut_grl_check_once']),
        ('X156i', ['spec', 'mut_bind_before_asyncio']),
        ('X117e', ['spec', 'mut_cm_resolve', 'mut_cm_get']),
        ('X117f', ['spec', 'mut_cm_smoke']),
        ('V72', ['spec', 'mut_guard_no_alive', 'mut_guard_never_held']),
        ('LEFTOVER', ['spec'])]

def prereg(path, gates):
    spec = {"gates": gates, "outcomes": [{"when": {k: True for k in gates}, "verdict": "PASS"}]
            + [{"when": {k: False}, "verdict": "FAIL_" + k} for k in gates], "smoke_verdict": "INVALID__smoke"}
    open(path, 'w').write('# r10\n\n```gates\n%s\n```\n' % json.dumps(spec, indent=1))

def main():
    src = open(REF, encoding='utf-8').read()
    print(sys.version.split()[0], 'ref_v5f.py sha256', hashlib.sha256(src.encode()).hexdigest()[:16])
    work = tempfile.mkdtemp(prefix='r10_')
    os.makedirs(os.path.join(work, 'fx')); repo = os.path.join(work, 'repo'); os.makedirs(repo)
    open(os.path.join(work, 'fx', 'fx_r10.py'), 'w').write(FIX)
    prereg(os.path.join(repo, 'PREREG_F.md'), {"G": {"metric": "m", "op": ">=", "value": 0.0, "exercises": ["fx_r10:f"]}})
    prereg(os.path.join(repo, 'PREREG_L.md'), {"G": {"metric": "m", "op": ">=", "value": 0.0, "exercises": ["fx_r10:cached_len"]}})
    prereg(os.path.join(repo, 'PREREG_S.md'), {"G": {"metric": "m", "op": ">=", "value": 0.0, "exercises": ["fx_r10:stamped_w"]}})
    prereg(os.path.join(repo, 'PREREG_N.md'), {"G": {"metric": "a.b", "op": ">=", "value": 0.0}})
    git = ['git', '-c', 'user.name=r10', '-c', 'user.email=r10@invalid', '-c', 'commit.gpgsign=false']
    subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
    subprocess.run(git + ['add', '.'], cwd=repo, check=True)
    subprocess.run(git + ['commit', '-q', '-m', 'p'], cwd=repo, check=True)
    for case, variants in PLAN:
        for v in variants:
            s = src
            for rep in MUTANTS[v]:
                old, new = rep[0], rep[1]
                if len(rep) == 3:
                    assert s.count(old) >= 1, (v, old); s = s.replace(old, new, 1)
                else:
                    assert s.count(old) == 1, (v, old, s.count(old)); s = s.replace(old, new)
            path = os.path.join(work, 'ref_%s.py' % v)
            open(path, 'w', encoding='utf-8').write(s)
            prog = os.path.join(work, 'case_%s.py' % case)
            open(prog, 'w').write(SETUP + CASES[case])
            r = subprocess.run([sys.executable, prog, work, path], capture_output=True, text=True, timeout=120)
            res = r.stdout.strip() or ('ERROR ' + (r.stderr.strip().splitlines() or ['?'])[-1])
            print('%-10s %-22s %s' % (case, v, res))

main()
