# Revision 7 self-audit: classes for every extracted claim (audit_claims.json, 305 hits in the normative text).
# P property of the mechanism; D disclosure / over-block / residual; C CPython fact relied on; G rule a gate or harness
# enforces by its own execution; H history, rationale, heading or quoted earlier text; N a case's own expected outcome;
# S a summary row (Delta, per-finding, closure) whose witness is named in its own row and in the section it summarizes.
import json, collections
o = json.load(open('audit_claims.json'))
P = {1,4,7,8,9,10,11,16,17,18,19,20,21,22,23,24,25,26,27,28,29,31,34,35,36,38,40,42,43,44,46,47,49,51,52,53,54,57,62,63,65,66,67,
     70,71,72,73,76,77,78,79,80,81,84,85,87,88,90,91,93,99,103,104,105,107,108,109,110,111,112,116,117,118,120,122,123,124,125,
     126,128,129,130,132,133,134,143,145,146,147,148,149,150,151,152,153,154,177,178,181,191,194,195,198,199}
D = {3,33,37,39,74,82,135,137,138,174,175,176,179,180,182,183,184,186,187,188,189,190,193,196,197}
C = {12,45,55,59,89,92,94,95,98,100,101,106,113,131,136,139,192,200}
H = {61,6,14,30,32,41,48,56,58,64,68,69,75,83,86,96,97,102,114,119,121,127,155,185}
G = {2,5,13,15,50,60,115,140,141,142,144}
cls = {}
for c in o:
    i = c['id']
    if i in P: k = 'P'
    elif i in D: k = 'D'
    elif i in C: k = 'C'
    elif i in H: k = 'H'
    elif i in G: k = 'G'
    elif c['top'] in ('Per-finding disposition (all 58 confirmed round-4 findings)', 'Finding closure, rounds 1–3 (rows that change; every other v5e row stands)'): k = 'S'
    elif c['top'] == 'Delta from v5e, section by section': k = 'S'
    elif c['top'] == 'Exam cases required':
        k = 'G' if c['sec'].startswith(('Exam harness rules', 'v5e cases whose outcome', 'Hazard sweeps', 'Mutation audit')) else 'N'
    elif c['top'].startswith(('The semantic-mutation gate', 'Process gates')): k = 'G'
    elif c['top'] == 'What round 5 should attack first': k = 'H'
    elif c['top'] == 'Cost': k = 'H'
    else: k = '?'
    cls[i] = k
    c['class'] = k
unk = [c for c in o if c['class'] == '?']
print('unclassified:', [(c['id'], c['sec'][:30]) for c in unk])
print(collections.Counter(cls.values()))
json.dump(o, open('audit_claims_classified.json', 'w'), indent=0)
with open('audit_claims_classified.txt', 'w') as f:
    for c in o: f.write('%d\t%s\tL%d\t[%s]\t%s\n' % (c['id'], c['class'], c['line'], c['sec'][:40], c['ctx']))
