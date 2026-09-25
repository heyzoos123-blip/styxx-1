# Builds the Revision 4 enumeration table from out_m1.txt.
import re, sys
sys.path.insert(0, '.')
from m1_pairs_modelcheck import CONFIGS
rows = {}
for l in open('out_m1.txt'):
    m = re.match(r'(.+?)\s{2,}(rev3-split|rev3|rev4)\s+faults<=(\d)\s+(\d+) states\s+(\d+)/(\d+)\s+ends\s+(.*?)(\s+\| outcomes.*)?\s+\(\d+s\)$', l.rstrip())
    if not m: continue
    cfg, rev, b, st, eff, ef, res = m.group(1).strip(), m.group(2), int(m.group(3)), int(m.group(4)), m.group(5), m.group(6), m.group(7)
    rows.setdefault(cfg, {}).setdefault(rev, []).append((b, st, res))
def cell(lst, ok_word='ok'):
    states = '/'.join('{:,}'.format(st) for b, st, res in sorted(lst))
    bad = [('f≤%d: ' % b) + res for b, st, res in sorted(lst) if res != 'ok']
    if not bad: return 'ok (%s states)' % states
    # show the fault-free violations, and the faulted ones only if new
    ff = [res for b, st, res in lst if b == 0 and res != 'ok']
    out = ff[0] if ff else bad[0]
    return '%s (%s states)' % (out.replace('_ff', ' ff').replace('_f', ' f').replace('=', ' '), states)
print('| configuration | concurrent transitions covered | rev 3 | rev 3, test and clear split | rev 4 |')
print('|---|---|---|---|---|')
for c in CONFIGS:
    r = rows.get(c.name, {})
    print('| %s | %s | %s | %s | %s |' % (c.name.replace('||', '∥'), '; '.join(c.pairs), cell(r.get('rev3', [])), cell(r.get('rev3-split', [])), cell(r.get('rev4', []))))
tot = sum(st for c in rows.values() for rev, lst in c.items() if rev == 'rev4' for b, st, res in lst)
print('\nrev4 total states', tot)
