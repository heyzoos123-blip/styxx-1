# verify8: the wider self-audit extraction (Appendix A, "Revision 8 notes on the method": nothing, no, none, only,
# every), over the normative text (title through "What round 5 should attack first"), at SENTENCE level.
# Output: wide_claims.json, one record per sentence that contains a wide keyword; 'old' marks sentences that also
# contain a revision-7 keyword (must, never, always, cannot, "0 violations").
import re, json, sys, collections
SRC = '/home/user/styxx-1/papers/first-afference/DESIGN_protocol_v5f_DRAFT_2026_09_25.md'
lines = open(SRC, encoding='utf-8').read().split('\n')
END = next(i for i, l in enumerate(lines) if l.startswith('## Decisions this synthesis is least sure of'))
WIDE = re.compile(r'\b(nothing|no|none|only|every)\b', re.I)
OLD = re.compile(r'\b(must|never|always|cannot)\b|0 violations', re.I)
SPLIT = re.compile(r'(?<=[.;!?])\s+(?=[A-Z*`(\[_"])|(?<=[a-z0-9`)*])\s*\|\s*(?=\S)|(?<=:)\s+(?=- )')
top = sec = ''
out = []; incode = False
for n, l in enumerate(lines[:END], 1):
    if l.startswith('```'): incode = not incode; continue
    if not incode and l.startswith('## '): top, sec = l[3:].strip(), ''; continue
    if not incode and l.startswith('### '): sec = l[4:].strip(); continue
    if not l.strip(): continue
    parts = [l] if incode else SPLIT.split(l)
    for s in parts:
        s = s.strip(' |')
        if not s: continue
        ks = sorted({m.group(1).lower() for m in WIDE.finditer(s)})
        if not ks: continue
        out.append(dict(id=len(out) + 1, line=n, top=top, sec=sec, code=incode, kw=ks, old=bool(OLD.search(s)), text=s))
json.dump(out, open('wide_claims.json', 'w'), indent=0, ensure_ascii=False)
print('normative region: lines 1..%d; sentences with a wide keyword: %d; of them also old-keyword: %d' % (
    END, len(out), sum(o['old'] for o in out)))
print(collections.Counter(o['top'] for o in out).most_common())
