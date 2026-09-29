"""Probe (exam author): does a freeze-count rise with no gc.freeze() call (3.12.3, after gc.unfreeze())
make ref_v5f.py record CLONE_ALIVE (b) for a harness that only holds M_T in a tuple?"""
import sys, runpy, gc
sys.argv = ['run_protocol_v5f_exam.py']
g = runpy.run_path(__import__('os').path.join(__import__('os').path.dirname(__import__('os').path.abspath(__file__)), '..', 'run_protocol_v5f_exam.py'), run_name='v5fexam')
P, EXP, fx, score = g['P'], g['EXP'], g['fx_v5f'], g['score']
for collect_inside in (False, True):
    gc.unfreeze()
    exp = EXP('F')
    keep = []
    with P.coverage_trace(exp) as cov:
        cov.run('G', fx.f)
        keep.append((fx.f.__code__,))          # the harness keeps M_T in a tuple (no function, no clone)
        if collect_inside:
            gc.collect()
    rec = cov.record()
    print(sys.version.split()[0], 'gc.collect() inside the trace:', collect_inside, '| freeze count', gc.get_freeze_count(),
          '| score', score(exp, rec)[:2], '| problems', [p[:60] for p in rec['problems']])
    keep.clear(); gc.collect()
