# Builds the Revision 5 enumeration table from out_m5_main.txt (one row per configuration).
import re, sys, collections
rows = collections.OrderedDict()
tot = {4: 0, 5: 0}; runs = {4: 0, 5: 0}
for line in open(sys.argv[1] if len(sys.argv) > 1 else 'out_m5_main.txt'):
    m = re.match(r'(.{46}) rev(\d) F(\d) I(\d) X(\d) W(\d)\s+(\d+) states\s+(\d+) ends\s+(.*?)\s+\(\d+s\)$', line.rstrip())
    if not m: continue
    name, rev, F, I, X, W, st, ends, res = m.groups()
    name = name.strip(); rev = int(rev)
    r = rows.setdefault(name, {4: [], 5: [], 'b': (I, X, W)})
    r[rev].append((int(F), int(st), res))
    tot[rev] += int(st); runs[rev] += 1
def cell(lst):
    states = '/'.join('{:,}'.format(s) for _, s, _ in lst)
    bad = [res for _, _, res in lst if not res.startswith('ok')]
    info = re.findall(r'\[(.*)\]', lst[-1][2])        # the largest budget's informational counts
    if bad:
        # the worst (largest fault budget) result, violations only
        worst = [res for _, _, res in lst if not res.startswith('ok')][-1]
        return '%s (%s states)' % (worst, states)
    return 'ok%s (%s states)' % ((' [' + '; '.join(info) + ']') if info else '', states)
print('| configuration | budgets (F / I / X / W) | rev 4 | rev 5 |')
print('|---|---|---|---|')
for name, r in rows.items():
    I, X, W = r['b']
    Fs = ','.join(str(f) for f, _, _ in r[5])
    print('| %s | %s / %s / %s / %s | %s | %s |' % (name.replace('||', '∥'), Fs, I, X, W, cell(r[4]), cell(r[5])))
print()
print('rev4 runs %d, %s state hashes; rev5 runs %d, %s state hashes' % (runs[4], '{:,}'.format(tot[4]), runs[5], '{:,}'.format(tot[5])))
