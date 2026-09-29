# rev10 (GAP-W triage): the three atoms of the 344 where a single-rule mutant of the reference survives every
# existing case, each with its new witness. Same method as p_rev10.py: a snapshot of v5f_exam/ref_v5f.py, mutants by
# exact replacement in memory, one fresh subprocess per (case, variant). Nothing under v5f_exam/ is written.
#   X10c  GAP-W011/W018: UNRESOLVED is chained `from e` at the import and at a PEP 562 __getattr__
#   X14d  GAP-W022: INHERITED names `?` for a defining class whose own-dict __module__ is not an exact str
#   V73   GAP-W183: an opening's notes are its fin notes, then o.lazy, then core.lost_note
# Run: <venv3.12|venv3.13>/bin/python p_rev10b.py
import hashlib, json, os, subprocess, sys, tempfile
REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'v5f_exam', 'ref_v5f.py')
MUTANTS = {
    'spec': [],
    'mut_import_no_chain': [('            f"{_TYPE_QUAL.__get__(type(e))}") from e\n', '            f"{_TYPE_QUAL.__get__(type(e))}")\n')],
    'mut_getattr_no_chain': [('f"({part!r}) raised {_TYPE_QUAL.__get__(type(e))}") from e', 'f"({part!r}) raised {_TYPE_QUAL.__get__(type(e))}")')],
    'mut_inherited_str': [("(dm if type(dm) is str else '?')", "str(dm)")],
    'mut_notes_order': [('notes.append(o.lazy)', 'notes.insert(0, o.lazy)')],
}
FIX = {
 'fx_r10b_boom.py': 'raise ValueError("boom at import")\n',
 'fx_r10b_lazy.py': 'def __getattr__(name):\n    raise KeyError(name)\n',
 'fx_r10b.py': 'def f(x=0): return x + 1\nclass Base:\n    def fit(self): return 1\nBase.__module__ = 5\nclass Sub(Base): pass\n',
}
SETUP = r'''
import sys, os, json, threading, importlib.util
WORK, SRC = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("ref_v5f", SRC)
P = importlib.util.module_from_spec(spec); sys.modules["ref_v5f"] = P; spec.loader.exec_module(P)
sys.path.insert(0, os.path.join(WORK, "fx"))
def EXP(k): return P.Experiment(os.path.join(WORK, "repo", "PREREG_%s.md" % k))
def code(e):
    s = str(e); return s[s.index("[V5:")+4:s.index("]")] if "[V5:" in s else type(e).__name__
'''
CASES = {
 'X10c': r'''
out = {}
for k in ("I", "A"):
    try:
        with P.coverage_trace(EXP(k)): pass
        out[k] = "no refusal"
    except P.GateSpecError as e:
        c = e.__cause__
        out[k] = [code(e), type(c).__name__ if c is not None else None]
print(json.dumps(out))
''',
 'X14d': r'''
try:
    with P.coverage_trace(EXP("H")): pass
    r = "no refusal"
except P.GateSpecError as e:
    s = str(e); r = [code(e), s[s.index("declare the defining class"):]]
print(json.dumps(r))
''',
 'V73': r'''
import fx_r10b
cov = P.coverage_trace(EXP("F")); inside = threading.Event(); go = threading.Event()
def gen():
    yield 1
def body():
    fx_r10b.f(); inside.set(); go.wait(10); return gen()
cov.__enter__()
t = threading.Thread(target=lambda: cov.run("G", body)); t.start(); inside.wait(10)
tool = P._v5_state()["tool"]
sys.monitoring.set_local_events(tool, fx_r10b.f.__code__, 0)   # an outside party blinds f: MONITOR_LOST at exit
cov.__exit__(None, None, None)                                   # G is still open: OPEN_AT_EXIT
go.set(); t.join(10)                                             # then fn returns a generator: LAZY_RESULT
rec = cov.record()
print(json.dumps([n.split("]")[0] + "]" for n in rec["sections"]["G"][0]["notes"]]))
''',
}
PLAN = [('X10c', ['spec', 'mut_import_no_chain', 'mut_getattr_no_chain']),
        ('X14d', ['spec', 'mut_inherited_str']),
        ('V73', ['spec', 'mut_notes_order'])]

def prereg(path, gates):
    spec = {"gates": gates, "outcomes": [{"when": {k: True for k in gates}, "verdict": "PASS"}]
            + [{"when": {k: False}, "verdict": "FAIL_" + k} for k in gates], "smoke_verdict": "INVALID__smoke"}
    open(path, 'w').write('# r10b\n\n```gates\n%s\n```\n' % json.dumps(spec, indent=1))

def main():
    src = open(REF, encoding='utf-8').read()
    print(sys.version.split()[0], 'ref_v5f.py sha256', hashlib.sha256(src.encode()).hexdigest()[:16])
    work = tempfile.mkdtemp(prefix='r10b_')
    os.makedirs(os.path.join(work, 'fx')); repo = os.path.join(work, 'repo'); os.makedirs(repo)
    for n, t in FIX.items(): open(os.path.join(work, 'fx', n), 'w').write(t)
    g = lambda ex: {"G": {"metric": "m", "op": ">=", "value": 0.0, "exercises": [ex]}}
    prereg(os.path.join(repo, 'PREREG_I.md'), g("fx_r10b_boom:f"))
    prereg(os.path.join(repo, 'PREREG_A.md'), g("fx_r10b_lazy:f"))
    prereg(os.path.join(repo, 'PREREG_H.md'), g("fx_r10b:Sub.fit"))
    prereg(os.path.join(repo, 'PREREG_F.md'), g("fx_r10b:f"))
    git = ['git', '-c', 'user.name=r10', '-c', 'user.email=r10@invalid', '-c', 'commit.gpgsign=false']
    subprocess.run(['git', 'init', '-q'], cwd=repo, check=True)
    subprocess.run(git + ['add', '.'], cwd=repo, check=True)
    subprocess.run(git + ['commit', '-q', '-m', 'p'], cwd=repo, check=True)
    for case, variants in PLAN:
        for v in variants:
            s = src
            for old, new in MUTANTS[v]:
                assert s.count(old) == 1, (v, old, s.count(old)); s = s.replace(old, new)
            path = os.path.join(work, 'ref_%s.py' % v); open(path, 'w', encoding='utf-8').write(s)
            prog = os.path.join(work, 'case_%s.py' % case); open(prog, 'w').write(SETUP + CASES[case])
            r = subprocess.run([sys.executable, prog, work, path], capture_output=True, text=True, timeout=120)
            res = r.stdout.strip() or ('ERROR ' + (r.stderr.strip().splitlines() or ['?'])[-1])
            print('%-6s %-22s %s' % (case, v, res))
main()
