# rev11 (GAP-37): the v5e cases v5f keeps, restated as spec data with each row's v5f expected outcome.
# Sources, read as data: the v5e design's "Exam cases required" tables (violation, valid, documented residuals, hazard
# sweeps) and the frozen v5e runner's case registrations (run_protocol_v5e.py: V[...] and R[...] with their expected
# outcome strings, and its docstring's list of ADDITIONS, which the v5e exam froze beside the design's tables).
# v5f's outcome for each row: the v5f text's delta table ("v5e cases whose outcome changes") and its private-name port
# table decide the rows they name; every other row keeps its v5e outcome (G_V5E_DELTA). Output: v5e_cases_kept.json.
import json, os, re
HERE = os.path.dirname(os.path.abspath(__file__))
FA = os.path.join(HERE, '..', '..')
DES = open(os.path.join(FA, 'DESIGN_protocol_v5e_mint_anchor_2026_09_24.md'), encoding='utf-8').read().split('\n')
RUN = open(os.path.join(FA, 'run_protocol_v5e.py'), encoding='utf-8').read()

def expand(idcell):
    idcell = re.sub(r'\s*\(.*?\)', '', idcell).strip()
    out = []
    for part in [p.strip() for p in idcell.split(',')]:
        m = re.fullmatch(r'([XVR])(\d+)[–-]\1?(\d+)', part)
        if m:
            w = len(re.match(r'[XVR](\d+)', part).group(1))
            out += ['%s%0*d' % (m.group(1), w, k) for k in range(int(m.group(2)), int(m.group(3)) + 1)]
        else:
            out.append(part)
    return out

# 1. the design's tables
shape, dexp, dsec = {}, {}, {}
sec = None
for l in DES:
    if l.startswith('### '): sec = l[4:].strip()
    if sec in ('Violation cases (expected code)', 'Valid cases (expected union counts)') and l.startswith('| ') and not l.startswith('| id'):
        c = [x.strip() for x in l.strip('|').split(' | ')]
        ids = expand(c[0]); shapes = [s.strip() for s in c[1].split(';')] if len(ids) > 1 else [c[1]]
        exps = [s.strip() for s in c[2].split(';')] if len(ids) > 1 else [c[2]]
        for i, k in enumerate(ids):
            shape[k] = shapes[i] if len(shapes) == len(ids) else c[1]
            dexp[k] = exps[i] if len(exps) == len(ids) else c[2]
            dsec[k] = sec
    if sec == 'Documented residuals (pinned outcome)' and l.startswith('- **R'):
        m = re.match(r'- \*\*(R\d+)\*\*(?: \((.*?)\))?: (.*?)\. Outcome: (.*)$', l)
        shape[m.group(1)] = m.group(3); dexp[m.group(1)] = m.group(4).rstrip('.'); dsec[m.group(1)] = sec
    if sec == 'Hazard sweeps, each paired with a detection mutant' and l.startswith('- **H'):
        m = re.match(r'- \*\*(H\d)\.\*\* (.*)$', l)
        shape[m.group(1)] = m.group(2); dexp[m.group(1)] = 'as stated in the shape'; dsec[m.group(1)] = sec

# 2. the runner's registrations and its ADDITIONS
reg = {}
for m in re.finditer(r'^\s*([VR])\["([A-Za-z0-9]+)"\] = \(\s*"((?:[^"\\]|\\.)*)"', RUN, re.M):
    reg[m.group(2)] = m.group(3)
reg.setdefault('X118', 'NOT_EXERCISED (P1 retro, G2 section)')
stmt = {}
lines = RUN.split('\n')
for i, l in enumerate(lines):
    m = re.match(r'^\s*[VR]\["([A-Za-z0-9]+)"\] = ', l)
    if m:
        buf, depth, j = [], 0, i
        while True:
            t = lines[j]; buf.append(t.strip())
            depth += t.count('(') - t.count(')') + t.count('[') - t.count(']') + t.count('{') - t.count('}')
            j += 1
            if depth <= 0 or j - i > 8: break
        stmt[m.group(1)] = ' '.join(buf)
doc = RUN.split('"""')[1]
add = {}
for m in re.finditer(r'\b([XV]\d+[a-z])(?:/([XV]\d+[a-z]))?\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)', doc):
    for k in (m.group(1), m.group(2)):
        if k: add.setdefault(k, m.group(3).replace('\n', ' '))
for rng, text in re.findall(r'(X108b-X108m|X104b-X104e) \(([^)]*)\)', doc):
    pass

# 3. v5f's decisions (the v5f text's delta and port tables)
DELTA = {
 'X75': ('retired', 'replaced by V49: PASS {f:1}, no note'),
 'X80': ('retired', 'replaced by V48: PASS {f:1}, profiler still installed and it saw the call'),
 'X81': ('retired', '3.11 is refused; V33 is unkeyed'),
 'V26': ('changed', '{f:1}, no note'),
 'V28': ('changed', '{f:1}, no note'),
 'V30': ('retired', 'no epochs; V28b covers hops'),
 'V31': ('retired', 'the leftover check requires getprofile()/gettrace() unchanged'),
 'X82': ('changed', 'unkeyed: runs on every verified interpreter (3.12+ only); outcome as v5e: NOT_EXERCISED (g), {f:1} recorded'),
 'V33': ('changed', 'unkeyed: runs on every verified interpreter; {f:1}'),
 'X95': ('kept', 'WRONG_TRACER; X95b adds /2 -> WRONG_TRACER'),
 'V34': ('changed', 'G0 declares the five frozen names of the v5f delta row; PASS, each union count >= 1; no exact _run count'),
 'X91': ('changed', 'TRACE_ACTIVE, text "the tracer was never entered"'),
 'X71c': ('ported', 'NOT_EXERCISED with the witness tracer\'s union {f:1}; the v5f port row (main thread before the self-trace, SIGALRM landing rule, 100,000 suspended openings)'),
 'H1': ('ported', 'sweep as v5e with no hang; detection mutant: the robust mutex replaced by threading.Lock (SM1 row against ref_v5f.py)'),
 'H2': ('ported', 'as v5e (20/20 propagated, 20/20 PASS); detection mutant: except Exception in the callbacks'),
 'H3': ('kept', '5/5 propagate; leaves no profile or trace function behind (v5f has none to leave)'),
 'H4': ('kept', 'reported, not gated'),
}
# sub-assertions of kept v5e rows that name v5e-only mechanism, and what v5f checks instead
SUBS = {
 'V21': 'the "no hooked threads left" part is the leftover check (v5f installs no hook)',
 'V27': 'no note (v5e allowed PROFILER_LOST; v5f has none)',
 'V32': 'the leftover check replaces "no leftovers"',
 'X92': 'the fault is injected as in v5e, by a profile function raising at the c_call of sys.getrefcount or gc.get_referrers on a thread the case owns; v5f\'s exit makes both calls in X6 (_clone_alive), after X1, so the outcome is TRACE_INCOMPLETE as in v5e',
 'X60': 'uncredited buckets pinned by the v5f attribution rule: a thread started in a section reaches its bootstrap (root): unattributed',
 'X61': 'as X60',
 'X80b': 'retired with FOREIGN_PROFILER (the NESTED part is X76\'s)',
 'X71': 'as v5e; X71c (ported) is the witness of the credit stop',
}
GROUP = {'X78d': 'open-check order: UNDECLARED before NESTED', 'X79c': 'open-check order: TRACE_INACTIVE before UNDECLARED',
         'X97b': 'targets a dict subclass', 'X97c': 'targets with str-subclass keys', 'X101b': 'an opening a dict subclass',
         'X104b': 'notes a tuple', 'X104c': 'a str-subclass note', 'X104d': 'a note without a code', 'X104e': 'notes a list subclass'}
for _k in ('X108b', 'X108c', 'X108d', 'X108e', 'X108f', 'X108g', 'X108h', 'X108i', 'X108j', 'X108k', 'X108m'):
    GROUP[_k] = 'one of calls, ambiguous, dispatched, unattributed as a dict subclass, with an int key, or with a str-subclass key; which one is fixed by its v5e_registration'
PLACE_MAIN = {'H1', 'H2', 'H3', 'X71c'}
rows = []
ids = sorted(set(reg) | set(shape), key=lambda k: (k[0], int(re.match(r'[A-Z](\d+)', k).group(1)), k))
for k in ids:
    status, v5f = DELTA.get(k, ('kept', None))
    v5e_out = reg.get(k) or dexp.get(k)
    if k == 'X80b': status = 'retired'
    rows.append({
        "id": k,
        "source": dsec.get(k) or ('v5e runner ADDITIONS (run_protocol_v5e.py docstring)' if k in add else 'v5e runner registration'),
        "shape": shape.get(k) or add.get(k) or GROUP.get(k) or '(see the v5e runner case of this id)',
        "v5e_outcome": v5e_out,
        "v5e_registration": stmt.get(k, ""),
        "status": status,
        "v5f_outcome": v5f if v5f else v5e_out,
        "v5f_sub_assertions": SUBS.get(k, "every sub-assertion the v5e runner makes for this id, as v5e"),
        "v5f_placement": 'main thread before the self-trace' if k in PLACE_MAIN else
                         ('in a fresh subprocess (as v5e)' if k in ('H1',) else 'inside the self-trace, as v5e places it (profiler-disturbing cases on a sub-thread the case owns)'),
    })
json.dump({"about": "revision 11 (GAP-37): the v5e cases v5f keeps, with each row's v5f outcome. Spec data.",
           "rules": ["A row with status 'kept' keeps its v5e id, shape, expected outcome and sub-assertions (G_V5E_DELTA: only the delta table's rows change).",
                     "'retired' rows are not run. 'changed' and 'ported' rows are run with v5f_outcome.",
                     "No kept row may carry a PROFILER_LOST, THREAD_HOP or FOREIGN_PROFILER code: those codes are retired, and a /3 trace carrying one is BAD_TRACE (X105d).",
                     "A v5e sub-assertion that reads a private name of styxx.protocol reads _v5_state() instead (the port table); the rows in v5f_sub_assertions say what replaces each."],
           "rows": rows}, open(os.path.join(HERE, 'v5e_cases_kept.json'), 'w'), indent=1, ensure_ascii=False)
import collections
print(len(rows), collections.Counter(r['status'] for r in rows), 'no shape:', [r['id'] for r in rows if r['shape'].startswith('(see')], 'no outcome:', [r['id'] for r in rows if not r['v5e_outcome']])
