# Revision 7: builds out_m7_table.md from out_m7_main.txt and out_m7_main_rebind2.txt (m7_modelcheck.py main / only).
import re, collections
rows = collections.OrderedDict(); tot = {6: [0, 0, 0], 7: [0, 0, 0]}
for fn in ('out_m7_main.txt', 'out_m7_main_rebind2.txt'):
    for line in open(fn):
        m = re.match(r'(.*?)\s+rev(\d) F(\d) I(\d) X(\d) W(\d)\s+(\d+) states\s+(\d+) ends\s+(.*?)\s+\(\d+s\)$', line.rstrip())
        if not m: continue
        name, rev, F = m.group(1).strip(), int(m.group(2)), int(m.group(3))
        states, verdict = int(m.group(7)), m.group(9)
        r = rows.setdefault(name, {'F': [], 'I': m.group(4), 'X': m.group(5), 'W': m.group(6), 6: [], 7: []})
        if F not in r['F']: r['F'].append(F)
        r[rev].append((states, verdict))
        tot[rev][0] += 1; tot[rev][1] += states; tot[rev][2] += 0 if verdict.startswith('ok') else 1
with open('out_m7_table.md', 'w') as out:
    out.write('| configuration | budgets (F / I / X / W) | rev 6 | rev 7 |\n|---|---|---|---|\n')
    for name, r in rows.items():
        def cell(v):
            verd = sorted(set(x[1] for x in v))
            return '%s (%s states)' % (' / '.join(verd), '/'.join('{:,}'.format(x[0]) for x in v))
        out.write('| %s | %s / %s / %s / %s | %s | %s |\n' % (name.replace('||', '∥'), ','.join(map(str, r['F'])), r['I'], r['X'], r['W'], cell(r[6]), cell(r[7])))
    out.write('\nconfigurations %d; runs: rev6 %d, rev7 %d; state hashes: rev6 %s, rev7 %s; runs with a violation: rev6 %d, rev7 %d\n' % (
        len(rows), tot[6][0], tot[7][0], '{:,}'.format(tot[6][1]), '{:,}'.format(tot[7][1]), tot[6][2], tot[7][2]))
print(open('out_m7_table.md').read()[-400:])
