# critic7 c2b: the same two-core configuration with a one-line fix (X5 counts a replaced callback in _LOST).
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import m6_fixcb as mc
mc.FIX_CB[0] = True
X, Y = 0, 1
cfgs = [mc.Cfg('c2 cb/local: open(Y) || exit(X)', [[mc.P('open', Y, 0)], [mc.P('exit', X)]], 2, '', ext=('cbrep',), X=1, faults=(0,))]
cfgs += [c for c in mc.CONFIGS if c.name.startswith('cb/local') or c.name.startswith('reg:')]
for cfg in cfgs:
    for b in mc.budgets(cfg, 6):
        r = mc.explore(cfg, 6, b)
        print('%-44s rev6+fix F%d X%d %8d states  %s' % (cfg.name, b[0], b[2], r['states'], mc.fmt(r)), flush=True)
