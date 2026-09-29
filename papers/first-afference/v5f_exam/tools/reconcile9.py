"""Reconcile the revision-9 rule atoms with Appendix A's classified lists (GAP-27).

Inputs (spec text and spec data only):
  - the design text (revision 9), through extract_rules9_base.py's output atoms9_raw.json;
  - protocol_v5f_design/rev9/appendix_a/wide_claims_classified.json (the revision-8 wide list);
  - protocol_v5f_design/rev9/appendix_a/rev9_new_sentences.json (sentences the wide extraction
    finds in the revision-9 text that the list lacks; unclassed).
The revision-7 list (protocol_v5f_design/rev7/audit_claims_classified.txt) is NOT read: the brief
limits this author to rev9/appendix_a/. Atoms whose wide-list row is class "old" (deferred to the
revision-7 list) are therefore classed by rule 2 and flagged.

Rules (Appendix A, "The classified lists are spec data"):
  1. an atom whose sentence is in a list takes that list's class and witnesses;
  2. any other atom is classed by Appendix A's table (P, D, C, G, N, S, H);
  3. every P, D or C atom that still names no witness is reported as a new gap.
"""
import json, re, hashlib, collections, sys

import os as _os
ROOT = _os.path.normpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), '..', '..')) + '/'
# usage: python tools/reconcile9.py RAW_ATOMS_JSON REV8_RULES_JSON OUT_RULES_JSON [--write]
#   (revision 9's reconciliation, kept as the receipt of commit 3002c140; revision 10 uses reconcile10.py)
_args = [a for a in sys.argv[1:] if not a.startswith('--')]
SPEC = ROOT + 'DESIGN_protocol_v5f_DRAFT_2026_09_25.md'
WIDE = ROOT + 'protocol_v5f_design/rev9/appendix_a/wide_claims_classified.json'
NEW9 = ROOT + 'protocol_v5f_design/rev9/appendix_a/rev9_new_sentences.json'
OLD = _args[1]   # the revision-8 atoms: git show 70a625ac:papers/first-afference/v5f_exam/rules_v5f.json
RAW = _args[0]
OUT = _args[2]
GAPS_OUT = OUT + '.gaps.json'

spec_text = open(SPEC, encoding='utf-8').read()
spec_lines = spec_text.split('\n')
raw = json.load(open(RAW))['rules']
wide = json.load(open(WIDE))
new9 = json.load(open(NEW9))
old_atoms = json.load(open(OLD))['rules']

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

# -- the Revision 9 table: GAP-nn -> its witnesses (Revision 9's own sentences name them there) -----
gap_rows = {}
for ln in spec_lines:
    m = re.match(r'^\| (GAP-\d\d) \|', ln)
    if m:
        cells = ln.split('|')
        res = cells[3] if len(cells) > 3 else ''
        gap_rows[m.group(1)] = wits(res)

# -- the lists -----------------------------------------------------------------------------------
wide_n = [(norm(x['text']), x) for x in wide]
new9_n = [(norm(x['text']), x) for x in new9]

def matches(an, lst):
    out = []
    for wn, x in lst:
        if len(wn) < 12:
            continue
        if wn in an or (len(an) >= 25 and an in wn):
            out.append(x)
    return out

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

# -- reconcile -------------------------------------------------------------------------------------
old_by_text = collections.defaultdict(list)
for a in old_atoms:
    old_by_text[norm(a['text'])].append(a['id'])

def line_of(a):
    key = norm(a['text'].split('\n')[0])[:50]
    if a['form'] == 'table_row':
        key = norm(a['text'].split(' | ')[0].split(': ', 1)[-1])[:40]
    for i, ln in enumerate(spec_lines):
        if key and key in norm(ln):
            return i + 1
    return None

PRI = {'P': 0, 'D': 1, 'C': 2, 'N': 3, 'G': 4, 'S': 5, 'H': 6}
out = []
for a in raw:
    an = norm(a['text'])
    wm = matches(an, wide_n)
    nm = matches(an, new9_n)
    b = {k: a[k] for k in ('id', 'section', 'form', 'text', 'keywords')}
    b['line'] = line_of(a)
    b['rev8_ids'] = old_by_text.get(an, [])
    own = wits(a['text'])
    ctx = a['witness_from_context']
    b['named_in_atom'] = own if any(own.values()) else None
    b['named_in_context'] = ctx
    listed = [x for x in wm if x['class'] != 'old']
    olds = [x for x in wm if x['class'] == 'old']
    if listed:
        # rule 1: the wide list's class and witnesses. Several list sentences in one atom (a table
        # row, a list item): the P/D/C ones win (the strictest duty), else the longest sentence's.
        pdc = [x for x in listed if x['class'] in 'PDC']
        pick = pdc if pdc else [max(listed, key=lambda x: len(x['text']))]
        cls = min((x['class'] for x in pick), key=PRI.get)
        ws = [x['witness'] for x in pick if x['class'] == cls and x['witness']]
        b['class'] = cls
        b['class_source'] = 'appendix_a_wide_list'
        b['list_ids'] = sorted(x['id'] for x in listed)
        b['witness'] = '; '.join(ws) if ws else None
        b['witness_source'] = 'appendix_a_wide_list' if ws else None
        # does the list's witness string name an id of the kind Appendix A's table admits?
        b['list_witness_names_id'] = bool(ws) and counts_for(cls, wits(b['witness']))
    else:
        cls = rule2(a)
        b['class'] = cls
        b['class_source'] = 'rule2_table' + ('_rev7_list_unread' if olds else '') \
            + ('_rev9_new_sentence' if nm else '')
        b['list_ids'] = sorted(x['id'] for x in olds)
        b['rev9_new_ids'] = sorted(x['id'] for x in nm)
        w, src = None, None
        if counts_for(cls, own):
            w, src = own, 'named_in_atom'
        else:
            gaps = sorted(set(re.findall(r'GAP-\d\d', a['text'])))
            gw = None
            if gaps:
                gw = {k: sorted(set(sum((gap_rows.get(g, {}).get(k, []) for g in gaps), [])))
                      for k in ('cases', 'gates', 'invariants', 'model_properties', 'controls', 'probes')}
            if gw and counts_for(cls, gw):
                w, src = gw, 'revision9_table:' + ','.join(gaps)
            elif ctx and counts_for(cls, dict(ctx, probes=wits('')['probes'])):
                w, src = ctx, 'named_in_context'
            elif cls == 'C':
                cw = wits(a['text'])
                if cw['probes']:
                    w, src = cw, 'named_in_atom'
        b['witness'] = ({k: v for k, v in w.items() if v} if w else None)
        b['witness_source'] = src
    b['needs_witness'] = b['class'] in 'PDC' and not b['witness']
    out.append(b)

gaps = [b for b in out if b['needs_witness']]
cnt = collections.Counter(b['class'] for b in out)
meta = {
    'spec': 'papers/first-afference/DESIGN_protocol_v5f_DRAFT_2026_09_25.md',
    'spec_revision': 9,
    'spec_sha256': hashlib.sha256(open(SPEC, 'rb').read()).hexdigest(),
    'scope': "title through 'What round 5 should attack first' (Appendix A's normative scope); "
             "'Verified in scratch' and 'Cost' excluded as measurement records",
    'extraction': 'one atom per sentence, list-item sentence, table row, or pseudocode function '
                  '(the revision-8 algorithm, re-run on the revision-9 text)',
    'reconciliation': (
        "Appendix A, 'The classified lists are spec data' (GAP-27). Rule 1: an atom containing a "
        "sentence of rev9/appendix_a/wide_claims_classified.json takes that list's class and "
        "witness string (several sentences in one atom: the P/D/C ones win, else the longest). "
        "Rule 2: every other atom is classed by Appendix A's table: the section rules for N, G, S, "
        "H and D, the Preamble (a summary of the design) is S, and within the mechanism sections a heading, list introduction or statement "
        "about an earlier revision or a critic is H, a measured CPython fact citing a probe is C, "
        "and the rest is P. Its witness is the case, gate clause, invariant, model property or "
        "control it names; else, for a sentence citing a revision-9 gap, the witnesses of that "
        "gap's row in the Revision 9 table; else those its enclosing paragraph, list item or row "
        "names; for C a probe also counts. Rule 3: every P, D or C atom with no witness has "
        "needs_witness true and is a Revision 9 follow-up gap in SPEC_GAPS.md. The revision-7 "
        "list was not read (outside the exam author's allowed reading), so atoms whose wide-list "
        "row defers to it (class 'old') are classed by rule 2 and marked "
        "class_source 'rule2_table_rev7_list_unread'."),
    'classes': {'P': 'property of the mechanism', 'D': 'disclosure (over-block, limit, residual)',
                'C': 'a fact about CPython the design relies on',
                'G': 'rule a gate/harness/exam author must follow', 'N': 'a case expected outcome',
                'S': 'summary row', 'H': 'history, rationale, heading or quoted earlier claim'},
    'counts': {
        'atoms': len(out),
        'by_class': {k: cnt.get(k, 0) for k in 'PDCGNSH'},
        'class_from_wide_list': sum(1 for b in out if b['class_source'] == 'appendix_a_wide_list'),
        'class_by_rule2': sum(1 for b in out if b['class_source'] != 'appendix_a_wide_list'),
        'rule2_rev7_list_unread': sum(1 for b in out if 'rev7_list_unread' in b['class_source']),
        'rule2_rev9_new_sentence': sum(1 for b in out if 'rev9_new_sentence' in b['class_source']),
        'with_witness': sum(1 for b in out if b['witness']),
        'PDC': sum(1 for b in out if b['class'] in 'PDC'),
        'PDC_with_witness': sum(1 for b in out if b['class'] in 'PDC' and b['witness']),
        'PDC_without_witness': len(gaps),
        'PDC_without_witness_by_class': dict(collections.Counter(b['class'] for b in gaps)),
        'witness_source': dict(collections.Counter(b['witness_source'] for b in out if b['witness'])),
        'PDC_list_witness_is_pointer': sum(1 for b in out if b['class'] in 'PDC' and b.get('list_witness_names_id') is False and b['witness']),
        'wide_list_sentences_matched': len({i for b in out if b['class_source'] == 'appendix_a_wide_list' for i in b['list_ids']}),
        'wide_list_sentences_total': len(wide),
    },
}
if '--write' in sys.argv:
    json.dump({'meta': meta, 'rules': out}, open(OUT, 'w'), indent=1, ensure_ascii=False)
json.dump(gaps, open(GAPS_OUT, 'w'), indent=1, ensure_ascii=False)
print(json.dumps(meta['counts'], indent=1))
