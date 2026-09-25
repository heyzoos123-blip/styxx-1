# Re-run m1_pairs_modelcheck (copied unchanged) for revision 4 only, every configuration, the published budgets.
import sys, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import m1_pairs_modelcheck as m
tot = 0
for cfg in m.CONFIGS:
    triple = len(cfg.threads) == 3
    for budget in ((0, 1) if triple else (0, 1, 2)):
        t0 = time.time(); r = m.explore(cfg, 4, False, budget); tot += r['states']
        print('%-34s faults<=%d %9d states  %s  (%.0fs)' % (cfg.name, budget, r['states'], m.fmt(r), time.time() - t0), flush=True)
print('total states', tot)
