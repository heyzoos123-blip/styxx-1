"""Extract rules_v5f.json from the v5f spec text (normative scope: title through
'What round 5 should attack first', the scope Appendix A's audits use)."""
import json, re, hashlib, sys
import os
_HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = os.path.join(_HERE, '..', '..', 'DESIGN_protocol_v5f_DRAFT_2026_09_25.md')
# usage: extract_rules.py [OUT]   (default: a raw atom file beside this script's caller, atoms_raw.json)
OUT = sys.argv[1] if len(sys.argv) > 1 else 'atoms_raw.json'
lines = open(SPEC, encoding='utf-8').read().split('\n')
end = next(i for i, l in enumerate(lines) if l.startswith('## Decisions this synthesis is least sure of'))
lines = lines[:end]
# Sections that record evidence or cost, not rules (kept out; their claims are measurements)
SKIP_HEADINGS = ('Verified in scratch, and what was not', 'Cost')
CASE = r'(?<![\w-])(?:X(?:\d{2,3}[a-z]?|\d{2,3}f)|V\d{2}[a-z]?|R\d{2}[a-z]?|H(?:10|[1-9]))(?![\w-])'
EXTRA_CASE = r'X137 (?:free|taken) variant|X137-free'
GATE = r'\bG_(?:SEM|REF|HYG|COVER|FI|SIG|XVER|INDEP|N|ATOM|V5E_DELTA|EXAM_FROZEN|CLOSURE|RED)\b|\bG[0-5]\b|\bSM[123]\b'
INV = r'(?<![\w-])(?:I[1-6]|U[1-4]|C[1-9])(?![\w-])'
MODEL = r'\b(?:LOSTNOTE|FALSEFLAG|STALE|CLOBBER|REGMULTI|REGSILENT|REGCLOB|HANG|REPAIR|CYC_OPEN|CYC_TX|VALUEERROR)\b|\bmodel(?:-check)? propert(?:y|ies)\b'
CTRL = r'(?<![\w-])K(?:1[0-4]|[1-9])b?(?![\w-])'
KEYS = ('must', 'never', 'always', 'cannot', 'only', 'every', 'no', 'none', 'nothing', 'iff',
        'refuse', 'refuses', 'raise', 'raises', 'exactly', 'forbidden', 'not')

def wits(t):
    return {
        'cases': sorted(set(re.findall(CASE, t)) | set(re.findall(EXTRA_CASE, t))),
        'gates': sorted(set(re.findall(GATE, t))),
        'invariants': sorted(set(re.findall(INV, t))),
        'model_properties': sorted(set(re.findall(MODEL, t))),
        'controls': sorted(set(re.findall(CTRL, t))),
    }

def empty(w):
    return not any(w.values())

def split_sentences(t):
    t = re.sub(r'\s+', ' ', t).strip()
    # split at ". " / "; " boundaries that end a sentence (not inside backticks), keep it simple
    parts, buf, tick = [], '', False
    i = 0
    while i < len(t):
        ch = t[i]
        buf += ch
        if ch == '`':
            tick = not tick
        if not tick and ch in '.!?' and i + 1 < len(t) and t[i + 1] == ' ' and (i + 2 < len(t) and (t[i + 2].isupper() or t[i + 2] in '*`(')):
            prev = buf[-6:]
            if not re.search(r'\b(?:e\.g|i\.e|vs|rev|cf|No|approx)\.$', buf) and not re.search(r'\d\.$', prev):
                parts.append(buf.strip()); buf = ''
        i += 1
    if buf.strip():
        parts.append(buf.strip())
    return parts

def kind_of(section, text):
    s = section
    if 'Exam harness rules' in s or 'Hazard sweeps' in s or 'Mutation audit' in s:
        return 'G'
    if s.startswith('Exam cases required') or 'violation cases' in s or 'valid cases' in s or 'residuals' in s or 'kill cases' in s or 'v5e cases' in s:
        return 'N' if not s.endswith('harness rules (frozen with the prereg before implementation)') else 'G'
    if 'Exam harness rules' in s or 'semantic-mutation gate' in s or 'SM1' in s or 'SM2' in s or 'SM3' in s or 'Positive controls' in s or 'Companion gates' in s or 'Process gates' in s or 'Frozen artifacts' in s or 'Hazard sweeps' in s or 'Mutation audit' in s:
        return 'G'
    if 'Delta from v5e' in s or 'Per-finding disposition' in s or 'Finding closure' in s or s.startswith(('Blockers', 'Spec-false', 'Defects', 'Note (1)', 'Exam holes', 'Round-4 items')):
        return 'S'
    if 'Over-blocking' in s or 'Stated limits' in s or 'Residuals, disclosed' in s:
        return 'D'
    if 'What round 5 should attack first' in s or 'P1 retro' in s:
        return 'H'
    return 'P'

atoms = []
heads = []          # stack of (level, title)
section = 'Preamble'
para = []           # (kind, lines) accumulated block
in_code = False
code_buf = []

def cur_section():
    return ' > '.join(h for _, h in heads) or 'Preamble'

def emit(text, block_text, form):
    text = text.strip()
    if not text or text in ('---',):
        return
    if re.fullmatch(r'[\|\-\s:]+', text):
        return
    w = wits(text)
    wc = wits(block_text) if empty(w) else None
    low = text.lower()
    kws = sorted({k for k in KEYS if re.search(r'\b' + re.escape(k) + r'\b', low)})
    atoms.append({
        'section': cur_section(),
        'form': form,
        'text': text,
        'kind': kind_of(cur_section(), text),
        'keywords': kws,
        'witness': w if not empty(w) else None,
        'witness_from_context': (wc if wc and not empty(wc) else None),
    })

def flush():
    global para
    if not para:
        return
    block = '\n'.join(para)
    first = para[0].lstrip()
    if any(h in cur_section() for h in SKIP_HEADINGS):
        para = []
        return
    if first.startswith('|'):
        rows = [r for r in para if r.strip().startswith('|')]
        header = None
        for r in rows:
            cells = [c.strip() for c in r.strip().strip('|').split('|')]
            if all(re.fullmatch(r':?-{3,}:?', c) for c in cells if c):
                continue
            if header is None:
                header = cells
                continue
            row_text = ' | '.join(f'{h}: {c}' for h, c in zip(header, cells))
            emit(row_text, row_text, 'table_row')
    elif re.match(r'^\s*(?:[-*]|\d+\.)\s', first):
        # list: each item (with its continuation lines) is one unit, split into sentences
        items, cur = [], []
        for l in para:
            if re.match(r'^\s*(?:[-*]|\d+\.)\s', l) and cur:
                items.append(' '.join(cur)); cur = []
            cur.append(l.strip())
        if cur:
            items.append(' '.join(cur))
        for it in items:
            it = re.sub(r'^(?:[-*]|\d+\.)\s+', '', it)
            for s in split_sentences(it):
                emit(s, it, 'list_item')
    else:
        for s in split_sentences(block):
            emit(s, block, 'sentence')
    para = []

for ln in lines:
    if ln.startswith('```'):
        if not in_code:
            flush(); in_code = True; code_buf = []
        else:
            in_code = False
            code = '\n'.join(code_buf)
            # one atom per top-level def (M6/M7 pseudocode), or one per block otherwise
            chunks = re.split(r'\n(?=def |async def )', code)
            for ch in chunks:
                if ch.strip() and not any(h in cur_section() for h in SKIP_HEADINGS):
                    atoms.append({'section': cur_section(), 'form': 'code', 'text': ch.strip(),
                                  'kind': 'P', 'keywords': [],
                                  'witness': {'cases': [], 'gates': ['G_HYG', 'G_ATOM'] if re.search(r'_unwind_on|_unwind_off|_take|_register|_set_local', ch) else ['G_HYG'],
                                              'invariants': [], 'model_properties': [], 'controls': []},
                                  'witness_from_context': None})
        continue
    if in_code:
        code_buf.append(ln); continue
    m = re.match(r'^(#{1,4})\s+(.*)', ln)
    if m:
        flush()
        lvl = len(m.group(1)); title = m.group(2).strip()
        while heads and heads[-1][0] >= lvl:
            heads.pop()
        if lvl > 1:
            heads.append((lvl, title))
        continue
    if not ln.strip():
        flush(); continue
    # a new list item or table row after prose starts a new block
    if para and (ln.lstrip().startswith('|') != para[0].lstrip().startswith('|')):
        flush()
    para.append(ln)
flush()

# ids: R-<section tag>-<n>, stable within this spec text
def tag(section):
    top = section.split(' > ')[0]
    m = re.match(r'^(M\d+|E\d)\b', section.split(' > ')[-1])
    base = re.sub(r'[^A-Za-z0-9]+', '_', top).strip('_')[:28]
    return (base + ('_' + m.group(1) if m else '')).upper()
counters = {}
for a in atoms:
    t = tag(a['section'])
    counters[t] = counters.get(t, 0) + 1
    a['id'] = f'R-{t}-{counters[t]:03d}'
normative = [a for a in atoms if a['kind'] != 'H']
summary = {
    'spec': 'papers/first-afference/DESIGN_protocol_v5f_DRAFT_2026_09_25.md',
    'spec_sha256': hashlib.sha256(open(SPEC, 'rb').read()).hexdigest(),
    'scope': "title through 'What round 5 should attack first' (Appendix A's normative scope); 'Verified in scratch' and 'Cost' excluded as measurement records",
    'extraction': 'one atom per sentence, list-item sentence, table row, or pseudocode function; witness = the case/gate/invariant/model-property ids named in the atom itself, else (witness_from_context) those named in its enclosing paragraph, list item or table row',
    'kinds': {'P': 'property of the mechanism', 'D': 'disclosure (over-block, limit, residual)', 'G': 'rule a gate/harness/exam author must follow', 'N': 'a case expected outcome', 'S': 'summary row', 'H': 'history/rationale (kept for completeness, not normative)'},
    'counts': {
        'atoms': len(atoms),
        'by_kind': {k: sum(1 for a in atoms if a['kind'] == k) for k in 'PDGNSH'},
        'with_own_witness': sum(1 for a in atoms if a['witness']),
        'with_context_witness_only': sum(1 for a in atoms if not a['witness'] and a['witness_from_context']),
        'no_named_witness': sum(1 for a in atoms if not a['witness'] and not a['witness_from_context']),
        'no_named_witness_P_D': sum(1 for a in atoms if a['kind'] in 'PD' and not a['witness'] and not a['witness_from_context']),
    },
}
json.dump({'meta': summary, 'rules': atoms}, open(OUT, 'w'), indent=1, ensure_ascii=False)
print(json.dumps(summary['counts'], indent=1))
