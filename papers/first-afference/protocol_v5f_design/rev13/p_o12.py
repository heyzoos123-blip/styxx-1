# rev13 (GAP-58): SM2's O12 "tuple rebuild -> in-place mutation", in the concrete form revision 13 states, applied
# to v5f_exam/ref_v5f.py (read only). Lists the O12 attribute names (attributes the module assigns only tuple values),
# builds one mutant per name in memory, and checks that it compiles, imports and runs a nested trace.
# Run: <venv3.12|venv3.13>/bin/python p_o12.py
import ast, importlib.util, json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, '..', '..', 'v5f_exam', 'ref_v5f.py')
src = open(REF, encoding='utf-8').read()
tree = ast.parse(src)

def kind(node, name):
    """The O12 form of an assignment value for attribute `name`, or None if it is not a tuple form."""
    v = node.value
    if isinstance(v, ast.Tuple): return 'display'
    if isinstance(v, ast.Call) and isinstance(v.func, ast.Name) and v.func.id == 'tuple' and len(v.args) == 1: return 'tuple_call'
    if (isinstance(v, ast.BinOp) and isinstance(v.op, ast.Add) and isinstance(v.left, ast.Attribute)
            and v.left.attr == name and isinstance(v.right, ast.Tuple)): return 'concat'
    return None

sites = {}
def visit(node, fname):
    for ch in ast.iter_child_nodes(node):
        if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
            visit(ch, ch.name); continue
        if isinstance(ch, ast.Assign) and len(ch.targets) == 1 and isinstance(ch.targets[0], ast.Attribute):
            n = ch.targets[0].attr
            sites.setdefault(n, []).append((ch, kind(ch, n), fname == '__init__'))
        visit(ch, fname)
visit(tree, None)
# an O12 name: every assignment of the attribute is a tuple form, and at least one is a rebuild outside __init__
names = sorted(n for n, ss in sites.items() if all(k is not None for _, k, _i in ss) and any(not i for _, _k, i in ss))

def mutate(name):
    lines = src.splitlines(keepends=True)
    edits = []
    for node, k, in_init in sites[name]:
        tgt = ast.get_source_segment(src, node.targets[0]); v = node.value
        if in_init:                                  # the creation site: a list instead of a tuple
            new = ('%s = [%s]' % (tgt, ', '.join(ast.get_source_segment(src, e) for e in v.elts)) if k == 'display'
                   else '%s = list(%s)' % (tgt, ast.get_source_segment(src, v.args[0])))
        elif k == 'display':                         # every rebuild: in place on the shared list
            new = '%s[:] = [%s]' % (tgt, ', '.join(ast.get_source_segment(src, e) for e in v.elts))
        elif k == 'tuple_call':
            new = '%s[:] = %s' % (tgt, ast.get_source_segment(src, v.args[0]))
        else:
            new = '%s.extend(%s)' % (tgt, ast.get_source_segment(src, v.right))
        edits.append((node.lineno, node.col_offset, node.end_lineno, node.end_col_offset, new))
    out = src
    # apply from the end, by absolute offsets
    offs = [0]
    for l in lines: offs.append(offs[-1] + len(l))
    for l0, c0, l1, c1, new in sorted(edits, reverse=True):
        a = offs[l0 - 1] + len(lines[l0 - 1][:c0].encode('utf-8').decode('utf-8'))
        b = offs[l1 - 1] + c1
        out = out[:a] + new + out[b:]
    return out, edits

PROG = r'''
import importlib.util, sys, os, json, threading
spec = importlib.util.spec_from_file_location("ref_v5f", sys.argv[1]); P = importlib.util.module_from_spec(spec)
sys.modules["ref_v5f"] = P; spec.loader.exec_module(P)
sys.path.insert(0, sys.argv[2]); import fx_o12 as fx
E = lambda k: P.Experiment(os.path.join(sys.argv[2], "PREREG_%s.md" % k))
outer = P.coverage_trace(E("f")); inner = P.coverage_trace(E("f"))
with outer:
    outer.run("G", fx.f)
    with inner: inner.run("G", fx.f)
    outer.run("G", fx.f)
r = [E("f").score({"m": 1.0, "coverage_trace": c.record()}).coverage for c in (outer, inner)]
st = P._v5_state()
print(json.dumps({"scores": r, "mints_after": st["mints"], "anchors": st["anchors"]}))
'''
work = tempfile.mkdtemp(prefix='o12_')
open(os.path.join(work, 'fx_o12.py'), 'w').write('def f(x=0):\n    return x + 1\n')
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.0, "exercises": ["fx_o12:f"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {"G": False}, "verdict": "FAIL"}], "smoke_verdict": "INVALID__s"}
open(os.path.join(work, 'PREREG_f.md'), 'w').write('# o12\n\n```gates\n%s\n```\n' % json.dumps(spec))
open(os.path.join(work, 'prog.py'), 'w').write(PROG)
git = ['git', '-c', 'user.name=r13', '-c', 'user.email=r13@invalid', '-c', 'commit.gpgsign=false']
subprocess.run(['git', 'init', '-q'], cwd=work, check=True); subprocess.run(git + ['add', 'PREREG_f.md'], cwd=work, check=True)
subprocess.run(git + ['commit', '-q', '-m', 'p'], cwd=work, check=True)
res = {'version': sys.version.split()[0], 'o12_attribute_names': names, 'mutants': {}}
for n in ['spec'] + names:
    s, edits = (src, []) if n == 'spec' else mutate(n)
    p = os.path.join(work, 'ref_%s.py' % n); open(p, 'w').write(s)
    compile(s, p, 'exec')
    r = subprocess.run([sys.executable, os.path.join(work, 'prog.py'), p, work], capture_output=True, text=True, timeout=120)
    res['mutants'][n] = {'sites': [(l0, new) for l0, c0, l1, c1, new in sorted(edits)],
                         'run': r.stdout.strip() or ('ERROR ' + (r.stderr.strip().splitlines() or ['?'])[-1])}
print(json.dumps(res, indent=1))
