# rev9 verifier: witnesses the design lacks, shown on the exam author's reference (read-only).
# Loads a snapshot of v5f_exam/ref_v5f.py (its sha256 is printed), builds single-rule mutants by exact string
# replacement in memory, and runs each (variant, case) in a fresh subprocess. Nothing under v5f_exam/ is written.
#   FA  GAP-16 (#128, #130, #528): X78f's variant counts only __eq__/__hash__, so it cannot see a section
#       rendered by repr() or a type name read through the metaclass. Extended variant counts both.
#   FB  over-blocking #23 (#132, #766): the disclosed NESTED_SECTION shape, built with
#       asyncio.events._set_running_loop (no pinned case in the design).
#   FC  GAP-09 (#203, #204): a refusal at step 6 binds nothing; the pre-C2 order (bind _MON before
#       import asyncio) differs observably at the next coverage_trace().
#   FD  GAP-02 (#194, #227): _get_running_loop re-checked at every coverage_trace(); X156g replaces it
#       before the first one, so a check-only-when-unbound mutant survives X156g.
#   FE  leftover check vs #498 (GAP-05): in a fresh process the "before" snapshot precedes the first
#       coverage_trace(); the fields that differ after one clean trace, against the harness rule
#       "`_v5_state()` equals the before snapshot, except the monotone fields `cut` and `tool`".
# Run: <venv3.12|venv3.13>/bin/python p_ref_findings.py
import hashlib, json, os, subprocess, sys, tempfile, textwrap

REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'v5f_exam', 'ref_v5f.py')

MUTANTS = {
    'spec': [],
    'mut_sec_repr': [('f"{_TYPE_QUAL.__get__(type(section))} is not a str;', 'f"{section!r} is not a str;')],
    'mut_sec_attrqual': [('f"{_TYPE_QUAL.__get__(type(section))} is not a str;', 'f"{type(section).__qualname__} is not a str;')],
    'mut_bind_before_asyncio': [
        ('    import asyncio                                   # M0 step 5 (GAP-09)\n',
         '    if _MON[0] is None:\n        _MON[0] = mon\n    import asyncio\n'),
    ],
    'mut_grl_check_once': [
        ('    if not (type(grl) is BuiltinFunctionType and grl.__name__ == "_get_running_loop"\n',
         '    if g.get("_get_running_loop") is None and not (type(grl) is BuiltinFunctionType and grl.__name__ == "_get_running_loop"\n'),
        ('    _get_running_loop = grl\n', '    if _get_running_loop is None:\n        _get_running_loop = grl\n'),
    ],
}

SETUP = r'''
import sys, os, json, types, subprocess, importlib.util, asyncio
WORK, SRC = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("ref_v5f", SRC)
P = importlib.util.module_from_spec(spec); sys.modules["ref_v5f"] = P; spec.loader.exec_module(P)
sys.path.insert(0, os.path.join(WORK, "fx"))
import fx_r9
def EXP(k): return P.Experiment(os.path.join(WORK, "repo", "PREREG_%s.md" % k))
def code(e):
    s = str(e); return s[s.index("[V5:")+4:s.index("]")] if "[V5:" in s else type(e).__name__
def score(exp, rec):
    try: v = exp.score({"m": 1.0, "coverage_trace": rec}); return ["PASS", v.coverage]
    except P.GateSpecError as e: return ["REFUSE", code(e)]
'''

CASES = {
 'FA_x78f_ext': r'''
cnt = {"eq": 0, "hash": 0, "repr": 0, "str": 0, "format": 0, "meta_qualname": 0}
class M(type):
    def __getattribute__(cls, n):
        if n == "__qualname__": cnt["meta_qualname"] += 1
        return type.__getattribute__(cls, n)
class Sec(metaclass=M):
    def __eq__(s, o): cnt["eq"] += 1; return False
    def __hash__(s): cnt["hash"] += 1; return 0
    def __repr__(s): cnt["repr"] += 1; return "Sec()"
    def __str__(s): cnt["str"] += 1; return "Sec"
    def __format__(s, spec): cnt["format"] += 1; return "Sec"
exp = EXP("F")
with P.coverage_trace(exp) as cov:
    try: cov.run(Sec(), fx_r9.f); r = "no refusal"
    except P.GateSpecError as e: r = code(e)
    cov.run("G", fx_r9.f)
x78f_variant_counters = cnt["eq"] + cnt["hash"]
print(json.dumps({"refusal": r, "counters": cnt, "x78f_variant_sees_it": x78f_variant_counters != 0,
                  "extended_variant_sees_it": sum(cnt.values()) != 0}))
''',
 'FB_overblock23': r'''
from asyncio import events
L1 = asyncio.new_event_loop()
exp, exp2 = EXP("F"), EXP("F")
out = {}
with P.coverage_trace(exp) as cov, P.coverage_trace(exp2) as cov2:
    def inner_same_core():
        events._set_running_loop(L1)          # the first loop runs again on the same stack
        try:
            try: cov.run("G", fx_r9.f); out["open_Q"] = "opened"
            except P.GateSpecError as e: out["open_Q"] = code(e)
            fx_r9.g()                          # a hit under P's anchor: the hit walk stops at P
        finally:
            events._set_running_loop(None)
    def middle_other_tracer():
        events._set_running_loop(None)        # P opens with another running loop (None)
        cov2.run("G", inner_same_core)
        events._set_running_loop(L1)
    events._set_running_loop(L1)              # O opens with L1 running
    try: cov.run("G", middle_other_tracer)
    finally: events._set_running_loop(None)
out["record_problems"] = [p[:60] for p in cov.record()["problems"]]
L1.close()
print(json.dumps(out))
''',
 'FC_order_step6': r'''
import asyncio.events as ev
orig = ev._get_running_loop
ev._get_running_loop = lambda: None
try:
    try: P.coverage_trace(EXP("F")); a = "constructed"
    except P.GateSpecError as e: a = code(e)
finally:
    ev._get_running_loop = orig
sm = sys.monitoring; orig_se = sm.set_events
def wrapper(*a): return orig_se(*a)
sm.set_events = wrapper                      # installed after the refused call, before any binding
try:
    try:
        with P.coverage_trace(EXP("F")) as cov: cov.run("G", fx_r9.f)
        b = score(EXP("F"), cov.record())
    except P.GateSpecError as e: b = ["RAISE", code(e)]
finally:
    sm.set_events = orig_se
print(json.dumps({"first": a, "_MON_bound_after_refusal": P._MON[0] is not None, "second_with_wrapper": b}))
''',
 'FE_leftover_first_trace': r'''
before = P._v5_state()
with P.coverage_trace(EXP("F")) as cov: cov.run("G", fx_r9.f)
after = P._v5_state()
differ = sorted(k for k in before if before[k] != after[k])
print(json.dumps({"differ": differ, "beyond_cut_and_tool": [k for k in differ if k not in ("cut", "tool")],
                  "tool_ours": [before["tool_ours"], after["tool_ours"]]}))
''',
 'FD_grl_every_trace': r'''
import asyncio.events as ev
with P.coverage_trace(EXP("F")) as cov: cov.run("G", fx_r9.f)
first = score(EXP("F"), cov.record())
orig = ev._get_running_loop
ev._get_running_loop = lambda: None           # replaced after the first binding
try:
    try:
        with P.coverage_trace(EXP("F")) as cov2: cov2.run("G", fx_r9.f)
        second = score(EXP("F"), cov2.record())
    except P.GateSpecError as e: second = ["RAISE", code(e)]
finally:
    ev._get_running_loop = orig
print(json.dumps({"first": first, "second_after_replacement": second}))
''',
}

PLAN = [('FA_x78f_ext', ['spec', 'mut_sec_repr', 'mut_sec_attrqual']),
        ('FB_overblock23', ['spec']),
        ('FC_order_step6', ['spec', 'mut_bind_before_asyncio']),
        ('FD_grl_every_trace', ['spec', 'mut_grl_check_once']),
        ('FE_leftover_first_trace', ['spec'])]

def main():
    src = open(REF, encoding='utf-8').read()
    print(sys.version.split()[0], 'ref_v5f.py sha256', hashlib.sha256(src.encode()).hexdigest()[:16])
    work = tempfile.mkdtemp(prefix='r9verify_')
    os.makedirs(os.path.join(work, 'fx')); os.makedirs(os.path.join(work, 'repo'))
    open(os.path.join(work, 'fx', 'fx_r9.py'), 'w').write('def f(x=0): return x + 1\ndef g(x=0): return x + 2\n')
    gates = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.0, "exercises": ["fx_r9:f"]}},
             "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {"G": False}, "verdict": "FAIL_G"}],
             "smoke_verdict": "INVALID__smoke"}
    open(os.path.join(work, 'repo', 'PREREG_F.md'), 'w').write('# r9\n\n```gates\n%s\n```\n' % json.dumps(gates, indent=1))
    git = ['git', '-c', 'user.name=r9', '-c', 'user.email=r9@invalid', '-c', 'commit.gpgsign=false']
    subprocess.run(['git', 'init', '-q'], cwd=os.path.join(work, 'repo'), check=True)
    subprocess.run(git + ['add', '.'], cwd=os.path.join(work, 'repo'), check=True)
    subprocess.run(git + ['commit', '-q', '-m', 'p'], cwd=os.path.join(work, 'repo'), check=True)
    for case, variants in PLAN:
        for v in variants:
            s = src
            for old, new in MUTANTS[v]:
                assert s.count(old) == 1, (v, old)
                s = s.replace(old, new)
            path = os.path.join(work, 'ref_%s.py' % v)
            open(path, 'w', encoding='utf-8').write(s)
            prog = os.path.join(work, 'case_%s.py' % case)
            open(prog, 'w').write(SETUP + CASES[case])
            r = subprocess.run([sys.executable, prog, work, path], capture_output=True, text=True, timeout=120)
            res = r.stdout.strip() or ('ERROR ' + r.stderr.strip().splitlines()[-1])
            print('%-20s %-24s %s' % (case, v, res))

main()
