# critic7 c2: m6_modelcheck.py's only 'cbrep' configuration has ONE core. Add the two-core shape: Y's section
# is open while X exits (X5's registration repairs the replaced callback); Y exits in the end phase.
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'run'))
import m6_modelcheck as mc
X, Y = 0, 1
cfgs = [mc.Cfg('c2 cb/local: open(Y) || exit(X)', [[mc.P('open', Y, 0)], [mc.P('exit', X)]], 2,
               'outside callback replacement, two tracers', ext=('cbrep',), X=1, faults=(0,)),
        mc.Cfg('c2 cb/local: open(Y) || exit(X) [lclr]', [[mc.P('open', Y, 0)], [mc.P('exit', X)]], 2,
               'outside local-events clear, two tracers', ext=('lclr',), X=1, faults=(0,))]
for cfg in cfgs:
    for rev in (5, 6):
        for b in mc.budgets(cfg, rev):
            r = mc.explore(cfg, rev, b)
            print('%-44s rev%d F%d X%d %8d states  %s' % (cfg.name, rev, b[0], b[2], r['states'], mc.fmt(r)), flush=True)
