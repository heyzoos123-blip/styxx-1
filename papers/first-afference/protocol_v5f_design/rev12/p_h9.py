# rev12 (GAP-49): H9's mutant, the X140 sweep, and which mutant shape #130279 really affects.
# Variants of v5f_exam/ref_v5f.py (read, never written), built in memory:
#   spec                 the reference
#   mut_h9_for_in_lock   revision 11's H9 text: X3's `for` loop inside `with _M:`, _exit_txn under `with _M:`
#   mut_h9_while_in_lock revision 12's H9: X3 as a `while` loop inside `with _M:`, _exit_txn under `with _M:`
# X140's trial set, per revision 12: every offset of _exit that lies in a loop (from a back-edge's target to the
# back-edge, inclusive). Each trial: a trace with two sections; the id-5 injector raises KeyboardInterrupt at the
# first execution of the offset during __exit__; then another thread runs a whole trace with a 5 s join.
# A trial HANGS if that thread does not finish (the with-exit was skipped and _M is still held).
# The old trial set (JUMP_BACKWARD offsets only) is reported too. One subprocess per variant.
import hashlib, json, os, subprocess, sys, tempfile
REF = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'v5f_exam', 'ref_v5f.py')
X3 = '''    for o in list(core.openings):                    # X3
        _detach(o, ("open", (f"[V5:OPEN_AT_EXIT] section {o.section!r} was still open when the "
                             f"trace exited; only calls confirmed before the exit count",)))
'''
TXT = '''("open", (f"[V5:OPEN_AT_EXIT] section {o.section!r} was still open when the "
                             f"trace exited; only calls confirmed before the exit count",))'''
LOCK = [('_monotonic, _sleep = time.monotonic, time.sleep', '_monotonic, _sleep = time.monotonic, time.sleep\n_M = threading.Lock()'),
        ('def _exit_txn(core):', 'def _exit_txn(core):\n    with _M:\n        return _exit_txn_inner(core)\n\n\ndef _exit_txn_inner(core):')]
MUTANTS = {
 'spec': [],
 'mut_h9_for_in_lock': LOCK + [(X3, '    with _M:\n        for o in list(core.openings):\n            _detach(o, ' + TXT + ')\n')],
 'mut_h9_while_in_lock': LOCK + [(X3, '    with _M:\n        _ops = list(core.openings); _i = 0\n        while _i < len(_ops):\n'
                                      '            o = _ops[_i]\n            _detach(o, ' + TXT + ')\n            _i += 1\n')],
}
CASE = r'''
import sys, os, dis, threading, importlib.util
WORK, SRC = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("ref_v5f", SRC)
P = importlib.util.module_from_spec(spec); sys.modules["ref_v5f"] = P; spec.loader.exec_module(P)
sys.path.insert(0, os.path.join(WORK, "fx")); import fx_r12
EXP = lambda: P.Experiment(os.path.join(WORK, "repo", "PREREG_F.md"))
M = sys.monitoring; E = M.events
code = P._exit.__code__
ins = list(dis.get_instructions(code))
back = [(i.offset, i.argval) for i in ins if i.opname in ('JUMP_BACKWARD', 'JUMP_BACKWARD_NO_INTERRUPT')]
in_loop = sorted({i.offset for i in ins for b, t in back if t <= i.offset <= b})
only_back = sorted(b for b, t in back)
def trial(off):
    st = {'armed': False, 'fired': False}
    def cb(c, o):
        if st['armed'] and c is code and o == off:
            st['armed'] = False; st['fired'] = True; raise KeyboardInterrupt
    M.use_tool_id(5, 'x140'); M.register_callback(5, E.INSTRUCTION, cb); M.set_local_events(5, code, E.INSTRUCTION)
    cov = P.coverage_trace(EXP()); cov.__enter__(); cov.run('G', fx_r12.f); cov.run('G', fx_r12.f)
    st['armed'] = True
    try: cov.__exit__(None, None, None)
    except KeyboardInterrupt: pass
    M.set_local_events(5, code, 0); M.register_callback(5, E.INSTRUCTION, None); M.free_tool_id(5)
    done = []
    def other():
        with P.coverage_trace(EXP()) as c2: c2.run('G', fx_r12.f)
        done.append(1)
    t = threading.Thread(target=other, daemon=True); t.start(); t.join(5)
    return st['fired'], bool(done)
res = {}
for name, offs in (('loop_body_set', in_loop), ('jump_backward_only', only_back)):
    hang = None; fired = 0
    for off in offs:
        f, ok = trial(off); fired += f
        if not ok: hang = off; break
    res[name] = {'offsets': len(offs), 'fired': fired, 'first_hang_at': hang}
print(res); sys.stdout.flush(); os._exit(0)
'''
def main():
    src = open(REF, encoding='utf-8').read()
    print(sys.version.split()[0], 'ref_v5f.py sha256', hashlib.sha256(src.encode()).hexdigest()[:16])
    work = tempfile.mkdtemp(prefix='r12h9_'); os.makedirs(os.path.join(work, 'fx')); repo = os.path.join(work, 'repo'); os.makedirs(repo)
    open(os.path.join(work, 'fx', 'fx_r12.py'), 'w').write('def f(x=0): return x + 1\n')
    spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.0, "exercises": ["fx_r12:f"]}},
            "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {"G": False}, "verdict": "FAIL"}], "smoke_verdict": "INVALID__s"}
    open(os.path.join(repo, 'PREREG_F.md'), 'w').write('# r12\n\n```gates\n%s\n```\n' % json.dumps(spec))
    git = ['git', '-c', 'user.name=r12', '-c', 'user.email=r12@invalid', '-c', 'commit.gpgsign=false']
    subprocess.run(['git', 'init', '-q'], cwd=repo, check=True); subprocess.run(git + ['add', '.'], cwd=repo, check=True)
    subprocess.run(git + ['commit', '-q', '-m', 'p'], cwd=repo, check=True)
    prog = os.path.join(work, 'case.py'); open(prog, 'w').write(CASE)
    for v, reps in MUTANTS.items():
        s = src
        for old, new in reps:
            assert s.count(old) == 1, (v, old[:40]); s = s.replace(old, new)
        path = os.path.join(work, 'ref_%s.py' % v); open(path, 'w').write(s)
        r = subprocess.run([sys.executable, prog, work, path], capture_output=True, text=True, timeout=900)
        print('%-22s %s' % (v, r.stdout.strip() or ('ERROR ' + (r.stderr.strip().splitlines() or ['?'])[-1])))
main()
