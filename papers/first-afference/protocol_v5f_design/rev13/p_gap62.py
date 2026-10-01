# rev13 (GAP-62): how many (operator family, region) cells SM1's "one weakening per operator family in each region"
# asks for, under two definitions of a region: each SM2 Region unit (a function or the M1 binding block, as
# opmut_v5f.py labels them), or each mechanism section M0-M11. Uses the exam author's opmut_v5f.py generator
# (read and run only) on v5f_exam/ref_v5f.py, and the catalog weakenings_v5f.py (to count the cells existing rows
# already fill). Run: <venv3.12>/bin/python p_gap62.py
import ast, collections, importlib.util, json, os, runpy, sys
HERE = os.path.dirname(os.path.abspath(__file__))
EXAM = os.path.join(HERE, '..', '..', 'v5f_exam')
sys.argv = [os.path.join(EXAM, 'opmut_v5f.py')]
sys.path.insert(0, EXAM)
spec = importlib.util.spec_from_file_location('opmut_v5f', os.path.join(EXAM, 'opmut_v5f.py'))
OM = importlib.util.module_from_spec(spec); spec.loader.exec_module(OM)
REF = os.path.join(EXAM, 'ref_v5f.py')
muts, labels, missing = OM.generate(REF)
SECTION = {}
for f in ('_txn', '_alive', '_acquire', '_release', '_locked'): SECTION[f] = 'M2 mutex'
for f in ('_reconcile', '_reclaim', '_prune', '_retire'): SECTION[f] = 'M3 reconciliation'
for f in ('_enter', '_enter_txn', '_ensure_tool', '_mint', '_resolve_target', '_own_dict', '_cache_callee',
          '_provenance', '_CoverageTracer.__enter__', 'coverage_trace', '_cut_refresh', '_cut_ok', '_cut_bind'): SECTION[f] = 'M0/M4 enter and resolution'
for f in ('_exit', '_exit_txn', '_clone_alive', '_CoverageTracer.__exit__'): SECTION[f] = 'M5 exit'
for f in ('_open', '_commit', '_run', '_run_async', '_detach', '_unwind_on', '_unwind_off', '_take', '_register',
          '_set_local', '_named', '_ours', '_lazy_text', '_CoverageTracer.run', '_CoverageTracer.run_async'): SECTION[f] = 'M7 sections and steps'
for f in ('_CoverageTracer.record',): SECTION[f] = 'M8 record'
for f in ('_forget_in_child',): SECTION[f] = 'M9 fork'
for f in ('_v5_state', '_v5_faultpoints'): SECTION[f] = 'M10 introspection'
for f in OM.SCORING: SECTION[f] = 'M11 scoring'
def sec(label):
    base = label.split('#')[0]
    if base in SECTION: return SECTION[base]
    if base.startswith('_on_') or base in ('_outcome', '_publish', '_hit', '_walk', '_attribute'): return 'M6 callbacks'
    if base.startswith('<module') or base.startswith('M1') or ':' in base: return 'M1 bindings'
    return 'other:' + base
by_unit = collections.defaultdict(set); by_sec = collections.defaultdict(set); unmapped = set()
for m in muts:
    if m['status'] != 'MUTANT': continue
    by_unit[m['family']].add(m['region']); s = sec(m['region']); by_sec[m['family']].add(s)
    if s.startswith('other:'): unmapped.add(m['region'])
fams = sorted(by_unit)
out = {'version': sys.version.split()[0], 'region_units': len(labels), 'mutants': sum(1 for m in muts if m['status'] == 'MUTANT'),
       'cells_per_unit': {f: len(by_unit[f]) for f in fams}, 'cells_per_unit_total': sum(len(by_unit[f]) for f in fams),
       'cells_per_section': {f: sorted(by_sec[f]) for f in fams}, 'cells_per_section_total': sum(len(by_sec[f]) for f in fams),
       'unmapped_units': sorted(unmapped)}
print(json.dumps(out, indent=1))

# the cells the existing catalog already fills: each row's family, and the Region unit holding its first patch
W = runpy.run_path(os.path.join(EXAM, 'weakenings_v5f.py'), run_name='w')['CATALOG']
src = open(REF, encoding='utf-8').read()
tree = ast.parse(src)
spans = []
def walk(node, prefix):
    for ch in ast.iter_child_nodes(node):
        if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
            spans.append((ch.lineno, ch.end_lineno, prefix + ch.name)); walk(ch, prefix + ch.name + '.')
        elif isinstance(ch, ast.ClassDef):
            walk(ch, prefix + ch.name + '.')
walk(tree, '')
def unit_at(line):
    best = None
    for a, b, n in spans:
        if a <= line <= b and (best is None or a >= best[0]): best = (a, n)
    return best[1] if best else '<module>'
filled = collections.defaultdict(set); rows_by_cell = collections.Counter()
for r in W:
    if not r.get('patches'): continue
    old = r['patches'][0][0]
    if src.count(old) != 1: continue
    line = src[:src.index(old)].count('\n') + 1
    s = sec(unit_at(line)); fam = r.get('family')
    filled[fam].add(s); rows_by_cell[(fam, s)] += 1
empty = {f: sorted(set(by_sec[f]) - filled.get(f, set())) for f in fams}
out2 = {'catalog_rows_with_patch': sum(rows_by_cell.values()),
        'cells_filled_by_existing_rows': sum(len(set(by_sec[f]) & filled.get(f, set())) for f in fams),
        'cells_empty': empty, 'cells_empty_total': sum(len(v) for v in empty.values())}
print(json.dumps(out2, indent=1))
print(json.dumps({'unit_sections': {l: sec(l) for l in labels}}, indent=1))
