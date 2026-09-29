"""Reconcile rules_v5f.json with Appendix A's three rules as revision 11 states them (exam author).

Revision 11 ("The three rules as revision 11 states them", GAP-32 to GAP-36):
  Rule 1: rev11/appendix_a/atom_witness_overrides_rev11.json FIRST (by atom id; it overrides
    everything below, the maps included), then rev11/appendix_a/rev9_new_sentences_classified_rev11.json
    (it supersedes the rev10 copy), rev10's wide_old_rows_resolved.json, the wide list, and the
    revision-7 list (class only); then pointer_witness_map.json and atom_witness_map.json by atom id.
  Rule 2 classes every atom no list and no map holds; being unlisted is NOT a gap (GAP-32).
  Rule 3, the witness test for every P, D or C atom, listed or not: a probe is a witness only for a
    C claim; a D claim is witnessed by a case or a pinned residual (a case id), or is filed as
    reading; a limit's name or an over-block's number is a pointer, not a witness.
Atom ids: an atom whose text equals a revision-10 atom's text keeps that id (so revision-9 ids, which
the maps and the overrides use, are kept); any other atom gets <tag>-R11-<n>.

Usage: python tools/reconcile11.py RAW_ATOMS_JSON REV10_RULES_JSON [--write] [--gaps OUT_JSON]
  REV10_RULES_JSON the revision-10 rules_v5f.json (git show 0e2d1e8b... or HEAD before this change)

The revision-10 docstring follows, for the parts revision 11 does not change.

Appendix A, "Rule 1's data, and what counts as a witness (revision 10)", and the Revision 10
section's "Required changes": re-run the reconciliation.
  Rule 1, in this order of precedence, by the sentence an atom contains:
    1. rev10/appendix_a/rev9_new_sentences_classified_rev10.json (witness_rev10 replaces witness;
       a row of class 'old' takes class_by_table / witness_by_table);
    2. rev10/appendix_a/wide_old_rows_resolved.json, for a wide-list row of class 'old';
    3. rev9/appendix_a/wide_claims_classified.json (the wide list);
    4. rev10/appendix_a/rev7_audit_claims_classified.json (class only; matched by the text around
       its keyword, since that list keeps a context window, not the sentence).
  Then, by atom id: pointer_witness_map.json (named witnesses for the 40 pointer atoms) and
  atom_witness_map.json (the 344 GAP-W atoms: resolution, witnesses, class_after).
  An atom that is P, D or C and has no witness naming a checkable object, or that appears in
  no list and no map, is reported.
Atom ids: an atom whose text equals a revision-9 atom's text keeps that id (the maps are keyed by
revision-9 ids); any other atom gets a new id <tag>-R10-<n>.

Usage: python tools/reconcile10.py RAW_ATOMS_JSON REV9_RULES_JSON [--write] [--gaps OUT_JSON]
  RAW_ATOMS_JSON  output of tools/extract_rules.py on the current text
  REV9_RULES_JSON the revision-9 rules_v5f.json (git show 99a2cc76:papers/first-afference/v5f_exam/rules_v5f.json)
"""
import json, re, hashlib, collections, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..')) + '/'
SPEC = ROOT + 'DESIGN_protocol_v5f_DRAFT_2026_09_25.md'
A9 = ROOT + 'protocol_v5f_design/rev9/appendix_a/'
A10 = ROOT + 'protocol_v5f_design/rev10/appendix_a/'
OUT = ROOT + 'v5f_exam/rules_v5f.json'

args = [a for a in sys.argv[1:] if not a.startswith('--')]
RAW, REV9 = args[0], args[1]          # REV9 here is the revision-10 rules file
GAPS_OUT = sys.argv[sys.argv.index('--gaps') + 1] if '--gaps' in sys.argv else None
if GAPS_OUT in args:
    args.remove(GAPS_OUT)

spec_text = open(SPEC, encoding='utf-8').read()
spec_lines = spec_text.split('\n')
raw = json.load(open(RAW))['rules']
rev9 = json.load(open(REV9))['rules']
A11 = ROOT + 'protocol_v5f_design/rev11/appendix_a/'
verif = json.load(open(A11 + 'rev9_new_sentences_classified_rev11.json'))['sentences']
overrides = json.load(open(A11 + 'atom_witness_overrides_rev11.json'))
wide = json.load(open(A9 + 'wide_claims_classified.json'))
wide_old = json.load(open(A10 + 'wide_old_rows_resolved.json'))
rev7 = json.load(open(A10 + 'rev7_audit_claims_classified.json'))
pmap = json.load(open(A10 + 'pointer_witness_map.json'))
amap = json.load(open(A10 + 'atom_witness_map.json'))

def norm(t):
    t = t.replace('*', '')
    t = re.sub(r'^\s*(?:[-]|\d+\.)\s+', '', t)
    return re.sub(r'\s+', ' ', t).strip()

# -- witnesses named in a text ---------------------------------------------------------------
CASE = r'(?<![\w-])(?:X\d{2,3}[a-z]?|V\d{2}[a-z]?|R\d{2}[a-z]?|H(?:10|[1-9]))(?![\w-])'
EXTRA_CASE = r'X137 (?:free|taken) variant|X137-free'
GATE = r'\bG_(?:SEM|REF|HYG|COVER|FI|SIG|XVER|INDEP|N|ATOM|V5E_DELTA|EXAM_FROZEN|CLOSURE|RED)\b|\bG[0-5]\b|\bSM[123]\b'
INV = r'(?<![\w-])(?:I[1-6]|U[1-4]|C[1-9])(?![\w-])'
MODEL = r'\b(?:LOSTNOTE|FALSEFLAG|STALE|CLOBBER|REGMULTI|REGSILENT|REGCLOB|HANG|REPAIR|CYC_OPEN|CYC_TX|VALUEERROR)\b|\bmodel(?:-check)? propert(?:y|ies)\b'
CTRL = r'(?<![\w-])K(?:1[0-4]|[1-9])b?(?![\w-])'
PROBE = r'(?:\b(?:rev\d|critic\d|synth|verify8|monitor|narrow|crashcons|design)/[\w./-]+|\b[\w-]+\.(?:py|txt)\b|\bD[123] p[\w_]+|\bp_[a-z_0-9]+\b)'

def wits(t):
    return {
        'cases': sorted(set(re.findall(CASE, t)) | set(re.findall(EXTRA_CASE, t))),
        'gates': sorted(set(re.findall(GATE, t))),
        'invariants': sorted(set(re.findall(INV, t))),
        'model_properties': sorted(set(re.findall(MODEL, t))),
        'controls': sorted(set(re.findall(CTRL, t))),
        'probes': sorted(set(re.findall(PROBE, t))),
    }

def counts_for(cls, w):
    """Does w name a witness of the kind Appendix A's table admits for class cls?"""
    if not w:
        return False
    if cls == 'C':
        return bool(w['probes'] or 'G_ATOM' in w['gates'] or w['gates'])
    return bool(w['cases'] or w['gates'] or w['invariants'] or w['model_properties'] or w['controls'])

# -- rule 2: Appendix A's table, read mechanically ------------------------------------------------
HIST_VERB = (r'said|was|were|had|ran|set|used|waited|tested|read|gave|made|relied|claimed|did|kept|'
             r'allowed|required|listed|left|put|named|added|dropped|built|bound|called|stored|'
             r'compared|checked|accepted|wrote|missed|passed|failed|broke|let|took|applied|moved|'
             r'placed|found|cleared|registered|proposed|raised|counted|repaired|scanned|gated|'
             r'covered|probed|measured|asked|chose|restricted|rejected|considered|lacked|split')
HIST = re.compile(r'\b(?:[Rr]evisions? \d+(?:[–-]\d+)?(?:,? (?:and|or) \d+)?|[Tt]he (?:\w+ )?critic(?:\'s)?|'
                  r'v5e|D[123]|[Jj]udge \d|the prototype)\b[^.;:]*?\b(?:' + HIST_VERB + r')\b')
HIST2 = re.compile(r'\b(?:[Rr]evisions? \d+|critic|judges?|[Jj]udge \d|prototype|v5e|revision-\d)\b')
PAST = re.compile(r'\b(?:' + HIST_VERB + r')\b')
MODAL = re.compile(r'\b(?:must|never|always|cannot|iff)\b')
CPY = re.compile(r'\b(?:CPython|3\.1[0-3](?:\.\d+)?|both versions|both verified|interpreter|'
                 r'eval-breaker|vectorcall|bytecode|audit event|PEP \d+|gc\b|GIL)\b')

def rule2(a):
    s = a['section']
    t = a['text']
    k = a['kind']                      # the section rules (same as Appendix A's section rules)
    if a['form'] == 'code':
        return 'P'
    if k not in 'PD':
        return k
    if s == 'Preamble':
        return 'S'                      # the preamble summarizes the design (a restatement)
    tn = norm(t)
    if re.fullmatch(r'\**[^*]{0,120}\**\.?:?', t.strip()) and t.strip().startswith('**') \
            and t.strip().rstrip('.:').endswith('**'):
        return 'H'                      # a bold heading alone
    if len(tn) < 70 and tn.endswith(':'):
        return 'H'                      # an introduction to a list
    if 'considered and rejected' in tn or 'was rejected' in tn:
        return 'H'
    if HIST.search(tn) and not re.search(r'\b(?:is|are|must|never|always|holds|refuses|raises|'
                                         r'returns|reads|runs|sets|takes|keeps|binds)\b', tn):
        return 'H'
    if HIST2.search(tn) and PAST.search(tn) and not MODAL.search(tn):
        return 'H'                      # a record of an earlier revision, critic, judge or prototype
    if re.fullmatch(r'`[^`]+ = [^`]+`;?', tn):
        return 'H'                      # a bare binding definition (G_HYG and the code atoms cover it)'
    if k == 'D':
        return 'D'
    w = wits(t)
    if w['probes'] and CPY.search(tn) and not (w['cases'] or w['model_properties']):
        return 'C'
    return 'P'


# -- what a witness is (Appendix A, revision 10, GAP-31) -------------------------------------------
MODEL_FILE = r'\b\w*model\w*\.py\b|\bcb2:|\breg2:'
LEFTOVER = r'\bleftover check\b'
MODEL_PROP_EXTRA = r'\bmodel\b[^;]*\b(?:END|P\d|U[1-4]|I[1-6]|configurations?|[a-z_]+\d?:)'
def expand_ranges(s):
    """'X01-X05' / 'X18–X25' -> 'X01, X05' so each end is a case id."""
    return re.sub(r'\b([XVR]\d{2,3}[a-z]?)[-–]([XVR]\d{2,3}[a-z]?)\b', r'\1, \2', s)
def checkable(cls, s):
    """Does witness string s name a checkable object: a case id, a gate and its clause, a model file
    with a property or configuration family, or (for C) a probe file? Appendix A's convention that
    "model" means the model-check file with the property named ("Model means m7_modelcheck.py
    (property named)") is applied, so "model U1" or a named invariant (U1-U4, I1-I6) counts."""
    if not s:
        return False
    s = expand_ranges(s)
    w = wits(s)
    if cls == 'D':                                    # rule 3 (revision 11): a case or a pinned residual
        return bool(w['cases'])
    if w['cases'] or w['gates'] or w['controls'] or re.search(LEFTOVER, s):
        return True
    if w['invariants'] or w['model_properties'] or re.search(MODEL_PROP_EXTRA, s):
        return True
    if re.search(MODEL_FILE, s) and (w['model_properties'] or re.search(r'propert|configuration|cb2|reg2|P\d|U\d|END', s)):
        return True
    if w['model_properties'] and re.search(r'\bmodel\b', s):
        return True
    if cls == 'C' and w['probes']:
        return True
    return False

def wstr(w):
    return '; '.join(f"{k}: {', '.join(v)}" for k, v in w.items() if v) if w else ''

# -- Appendix A's revision-7 tables: witness by revision-7 audit id -------------------------------------
def rev7_witness_table():
    """Appendix A's "The P, D and C claims and their witnesses" (claim (ids) | class | witness) and
    the findings table A1-A16 (claim (...; ids n, m) | before | action): audit id -> witnesses."""
    out = collections.defaultdict(list)
    s = next(i for i, l in enumerate(spec_lines) if l.startswith('**The P, D and C claims and their witnesses.**'))
    for l in spec_lines[s + 1:]:
        if not l.startswith('|'):
            if l.strip():
                break
            continue
        c = [x.strip() for x in l.strip().strip('|').split('|')]
        if len(c) < 4 or c[0] in ('section', '---') or set(c[0]) <= set('-'):
            continue
        for g in re.findall(r'\((\d+(?:, \d+)*)\)', c[1]):
            for i in re.findall(r'\d+', g):
                out[int(i)].append(c[3])
    f = next(i for i, l in enumerate(spec_lines) if l.startswith('| # | claim (section; audit ids)'))
    for l in spec_lines[f + 2:]:
        if not l.startswith('|'):
            break
        c = [x.strip() for x in l.strip().strip('|').split('|')]
        for g in re.findall(r'ids? (\d+(?:, \d+)*)', c[1]):
            for i in re.findall(r'\d+', g):
                out[int(i)].append(c[3])
    return out
REV7_WIT = rev7_witness_table()

# -- 'definition' rows of atom_witness_map.json the exam author disputes (Revision 10, weakest point 2) --
# Each is a disclosure (class D by Appendix A's table), not a data layout, a step name or a heading, and
# its witnesses name no checkable object under the revision-10 definition (a limit's name, a probe for a
# non-C claim, or nothing). The map's class is kept in 'class'; the dispute is recorded beside it.
DISPUTED_DEFINITIONS = {   # revision 10's disputes; revision 11 rules on each in the overrides file (GAP-36)
    'R-TARGET_IDENTITY-111': 'D: freeze0 can predate the trace (a disclosure); "over-blocking #19" is a list item, not a pinned case',
    'R-TARGET_IDENTITY-130': 'D: a disclosed door of L-CLONE; "R-rows of the residual table" names no residual id',
    'R-TARGET_IDENTITY-131': 'D: a disclosed door of L-CLONE (exec of M_T); "L-CLONE" names no residual id',
    'R-TARGET_IDENTITY-132': 'D: a disclosed door of L-CLONE (a swap-and-restore); "L-CLONE" names no residual id',
    'R-TARGET_IDENTITY-134': 'D: when the freeze count does not rise; a probe witnesses only C claims',
    'R-MECHANISM_AND_LIFECYCLE_M1-061': 'D: a dead retained frame keeps its callers alive; limit names only',
    'R-MECHANISM_AND_LIFECYCLE_M3-020': 'D: a foreign tool\'s events and callbacks stay on the id for the process; "L-MONITOR" only',
    'R-MECHANISM_AND_LIFECYCLE_M11-028': 'D: check_metrics can run two kinds of user method; a probe witnesses only C claims',
    'R-MECHANISM_AND_LIFECYCLE_M11-029': 'D (or C): "a JSON-loaded result has exact-str keys"; no witness at all',
    'R-EXCEPTION_SAFETY_MODEL-119': 'D: the kept frame keeps its callers alive until then; "L-MONITOR" only',
}

# -- the Revision 9 and Revision 10 tables: GAP-nn / R9-n -> the witnesses its row names ----------------
gap_rows = {}
for ln in spec_lines:
    m = re.match(r'^\| (GAP-\d\d|GAP-W\d+[^|]*|R9-\d+)[^|]*\|', ln)
    if m:
        cells = ln.split('|')
        gap_rows[m.group(1).strip()] = ' '.join(cells[3:])

# -- rule 1's lists --------------------------------------------------------------------------------
def entries(rows, textkey='text'):
    return [(norm(x[textkey]), x) for x in rows if len(norm(x[textkey])) >= 12]

verif_n = entries(verif)
wide_n = entries(wide)
def contains(an, lst):
    return [x for xn, x in lst if xn in an or (len(an) >= 25 and an in xn)]

def rev7_key(x):
    c = norm(x['ctx']); w = x['word'].lower()
    idx = [m.start() for m in re.finditer(r'\b' + re.escape(w) + r'\b', c.lower())]
    if not idx:
        return None
    mid = min(idx, key=lambda i: abs(i - len(c) // 2))
    lo, hi = max(0, mid - 28), min(len(c), mid + len(w) + 28)
    return c[lo:hi]
rev7_n = [(rev7_key(x), x) for x in rev7]
rev7_n = [(k, x) for k, x in rev7_n if k]

PRI = {'P': 0, 'D': 1, 'C': 2, 'N': 3, 'G': 4, 'S': 5, 'H': 6}
def pick(rows, clsf, witf):
    """Several rows of one list in one atom: the P/D/C rows win (the strictest duty), else the
    longest row; witnesses of the winning class are joined."""
    cl = [(clsf(x), witf(x), x) for x in rows]
    pdc = [c for c in cl if c[0] in ('P', 'D', 'C')]
    use = pdc if pdc else [max(cl, key=lambda c: len(c[2].get('text', c[2].get('ctx', ''))))]
    cls = min((c[0] for c in use), key=lambda k: PRI.get(k, 9))
    ws = [c[1] for c in use if c[0] == cls and c[1]]
    return cls, '; '.join(dict.fromkeys(ws)) or None

def v_cls(x):
    return x['class_by_table'] if x['class'] == 'old' else x['class']
def v_wit(x):
    if x.get('witness_rev10'):
        return x['witness_rev10']
    return x.get('witness_by_table') if x['class'] == 'old' else x.get('witness')

# -- ids: keep revision-9 ids for unchanged texts ---------------------------------------------------
by_text9 = collections.defaultdict(list)
for a in rev9:
    by_text9[(a['section'], norm(a['text']))].append(a['id'])
by_text9_any = collections.defaultdict(list)
for a in rev9:
    by_text9_any[norm(a['text'])].append(a['id'])
used = set()
newn = collections.Counter()
def assign_id(a):
    an = norm(a['text'])
    for pool in (by_text9.get((a['section'], an), []), by_text9_any.get(an, [])):
        for i in pool:
            if i not in used:
                used.add(i)
                return i, True
    tag = re.sub(r'-(?:R1[01]-)?\d{3}$', '', a['id'])
    newn[tag] += 1
    tag = re.sub(r'-R1[01]$', '', tag)
    return f"{tag}-R11-{newn[tag]:03d}", False

def line_of(a):
    key = norm(a['text'].split('\n')[0])[:50]
    if a['form'] == 'table_row':
        key = norm(a['text'].split(' | ')[0].split(': ', 1)[-1])[:40]
    for i, ln in enumerate(spec_lines):
        if key and key in norm(ln):
            return i + 1
    return None

out = []
for a in raw:
    an = norm(a['text'])
    aid, kept = assign_id(a)
    b = {'id': aid, 'id_from_rev9': kept}
    b.update({k: a[k] for k in ('section', 'form', 'text', 'keywords')})
    b['line'] = line_of(a)
    own = wits(a['text'])
    ctx = a['witness_from_context']
    b['named_in_atom'] = own if any(own.values()) else None
    b['named_in_context'] = ctx
    src, cls, wit = None, None, None
    vm = contains(an, verif_n)
    wm = contains(an, wide_n)
    wold = [x for x in wm if x['class'] == 'old' and str(x['id']) in wide_old]
    wnew = [x for x in wm if x['class'] != 'old']
    r7 = [x for k, x in rev7_n if k in an]
    if vm:
        cls, wit = pick(vm, v_cls, v_wit); src = 'rule1:rev9_new_sentences_classified_rev11'
    elif wold:
        rows = [dict(wide_old[str(x['id'])], id=x['id']) for x in wold]
        cls, wit = pick(rows, lambda x: x['class'], lambda x: x['witness']); src = 'rule1:wide_old_rows_resolved'
    elif wnew:
        cls, wit = pick(wnew, lambda x: x['class'], lambda x: x['witness']); src = 'rule1:wide_list'
    elif r7:
        cls, wit = pick(r7, lambda x: x['class'],
                        lambda x: '; '.join(REV7_WIT.get(x['id'], [])))
        src = 'rule1:rev7_list' + ('' if wit else ' (class only)')
        if wit:
            b['witness_source'] = "Appendix A's revision-7 tables, by audit id"
    b['list_source'] = src
    b['list_ids'] = {'verifier': sorted(x['id'] for x in vm), 'wide': sorted(x['id'] for x in wm),
                     'rev7': sorted(x['id'] for x in r7)}
    b.setdefault('witness_source', src)
    b['map'] = None
    if aid in pmap:
        b['map'] = 'pointer_witness_map'
        wit = pmap[aid]
        b['witness_source'] = 'pointer_witness_map'
    if aid in amap:
        m = amap[aid]
        b['map'] = 'atom_witness_map'
        b['map_resolution'] = m['resolution']
        b['map_gap'] = m['gap']
        b['map_text_matches'] = norm(m['text']) == an
        cls = m['class_after']
        b['witness_source'] = 'atom_witness_map'
        if aid in DISPUTED_DEFINITIONS:
            b['disputed_by_exam_author'] = DISPUTED_DEFINITIONS[aid]
        wit = ', '.join(m['witnesses']) + (f" ({m['resolution']}: {m['note']})" if m.get('note') else '')
    if aid in overrides:                              # rule 1, first in order: revision 11's rulings
        o = overrides[aid]
        b['override_rev11'] = o['gap']
        cls, wit = o['class'], o['witness']
        b['witness_source'] = 'atom_witness_overrides_rev11'
        b['map'] = 'atom_witness_overrides_rev11'
    if cls is not None and not checkable(cls, wit or '') and cls in ('P', 'D', 'C'):
        # the rule-1 or map witness names nothing checkable: the atom's own named witness, if any
        if counts_for(cls, own):
            b['witness_rule1_not_checkable'] = wit
            wit = wstr(own); b['witness_source'] = 'named_in_atom (rule-1 witness not checkable)'
    if cls is None:                                   # rule 2 (no list, no map)
        cls = rule2(a)
        if counts_for(cls, own):
            wit = wstr(own); b['witness_source'] = 'named_in_atom'
        elif re.search(r'GAP-\d\d|R9-\d+', a['text']) and any(
                checkable(cls, gap_rows.get(g, '')) for g in re.findall(r'GAP-\d\d|R9-\d+', a['text'])):
            gs = sorted(set(re.findall(r'GAP-\d\d|R9-\d+', a['text'])))
            wit = wstr(wits(expand_ranges(' '.join(gap_rows.get(g, '') for g in gs))))
            b['witness_source'] = 'revision 9/10 table row: ' + ', '.join(gs)
        elif ctx and counts_for(cls, dict(ctx, probes=[])):
            wit = wstr(ctx); b['witness_source'] = 'named_in_context'
        elif cls == 'C' and own['probes']:
            wit = wstr(own); b['witness_source'] = 'named_in_atom'
    b['class'] = cls
    b['class_source'] = ('map:' + b['map']) if b['map'] in ('atom_witness_map', 'atom_witness_overrides_rev11') else (src or 'rule2_table')
    b['witness'] = wit or None
    b['witness_checkable'] = checkable(cls, wit or '')
    # a 'reading' disposition (Appendix A: R9-7, F37, F38, and revision 7's untestable D claim) is a
    # resolution the spec accepts without an executable witness; it is counted apart
    b['witness_is_reading'] = (not b['witness_checkable'] and bool(wit)
                               and (b.get('map_resolution') == 'reading' or re.match(r'\s*reading\b', wit or '') is not None))
    b['listed'] = bool(src or b['map'])
    b['needs_witness'] = cls in ('P', 'D', 'C') and not b['witness_checkable'] and not b['witness_is_reading']
    out.append(b)

KW = re.compile(r'\b(?:nothing|no|none|only|every|must|never|always|cannot)\b', re.I)
for b in out:
    b['has_list_keyword'] = KW.search(b['text']) is not None
gaps = [b for b in out if b['needs_witness']]
unlisted = [b for b in out if not b['listed']]
cnt = collections.Counter(b['class'] for b in out)
mapped_ids = set(pmap) | set(amap)
present_ids = {b['id'] for b in out}
C = {
    'atoms': len(out),
    'ids_kept_from_rev9': sum(b['id_from_rev9'] for b in out),
    'ids_new_in_rev11': sum(not b['id_from_rev9'] for b in out),
    'overrides_rev11_applied': sorted(b['id'] for b in out if b.get('override_rev11')),
    'overrides_rev11_not_found': sorted(set(overrides) - {b['id'] for b in out}),
    'by_class': {k: cnt.get(k, 0) for k in 'PDCGNSH'},
    'by_source': dict(collections.Counter(b['class_source'] for b in out)),
    'map_ids_not_found_in_rev11_atoms': sorted(mapped_ids - present_ids),
    'atom_map_text_mismatch': sorted(b['id'] for b in out if b.get('map_text_matches') is False),
    'atom_map_by_resolution': dict(collections.Counter(b['map_resolution'] for b in out if b.get('map_resolution'))),
    'PDC': sum(1 for b in out if b['class'] in 'PDC'),
    'PDC_with_checkable_witness': sum(1 for b in out if b['class'] in 'PDC' and b['witness_checkable']),
    'PDC_without_witness': len(gaps),
    'PDC_without_witness_by_class': dict(collections.Counter(b['class'] for b in gaps)),
    'PDC_without_witness_by_source': dict(collections.Counter(b['class_source'] for b in gaps)),
    'PDC_resolved_by_reading': sum(1 for b in out if b['class'] in 'PDC' and b['witness_is_reading']),
    'definition_rows_disputed': sorted(DISPUTED_DEFINITIONS),
    'unlisted': len(unlisted),
    'unlisted_with_list_keyword': sum(1 for b in unlisted if KW.search(b['text'])),
    'unlisted_by_class': dict(collections.Counter(b['class'] for b in unlisted)),
    'unlisted_new_in_rev11': sum(1 for b in unlisted if not b['id_from_rev9']),
    'unlisted_is_not_a_gap': 'revision 11, GAP-32',
    'unlisted_with_witness': sum(1 for b in unlisted if b['witness']),
}
meta = {
    'spec': 'papers/first-afference/DESIGN_protocol_v5f_DRAFT_2026_09_25.md',
    'spec_revision': 11,
    'spec_sha256': hashlib.sha256(open(SPEC, 'rb').read()).hexdigest(),
    'scope': "title through 'What round 5 should attack first' (Appendix A's normative scope); "
             "'Verified in scratch' and 'Cost' excluded as measurement records",
    'extraction': 'tools/extract_rules.py: one atom per sentence, list-item sentence, table row, or '
                  'pseudocode function',
    'reconciliation': __doc__.strip(),
    'classes': {'P': 'property of the mechanism', 'D': 'disclosure (over-block, limit, residual)',
                'C': 'a fact about CPython the design relies on',
                'G': 'rule a gate/harness/exam author must follow', 'N': 'a case expected outcome',
                'S': 'summary row, definition or restatement', 'H': 'history, rationale or heading'},
    'counts': C,
}
if '--write' in sys.argv:
    json.dump({'meta': meta, 'rules': out}, open(OUT, 'w'), indent=1, ensure_ascii=False)
if GAPS_OUT:
    json.dump({'needs_witness': gaps, 'unlisted': unlisted}, open(GAPS_OUT, 'w'), indent=1, ensure_ascii=False)
print(json.dumps(C, indent=1))
