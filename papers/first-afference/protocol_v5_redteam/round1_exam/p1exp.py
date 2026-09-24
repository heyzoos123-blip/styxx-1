import sys, json, collections
sys.argv=['x','--attempt-b']
sys.path.insert(0,'papers/first-afference')
import run_protocol_v5 as R
import numpy as np, importlib.util
pw = R._load_quarantined_power()
spec = importlib.util.spec_from_file_location("run_p1", R.HERE / "run_p1.py")
p1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(p1)
# 1. full trace of every function in the quarantined module during degenerate()
codes = {v.__code__: k for k, v in vars(pw).items() if callable(v) and hasattr(v, '__code__')}
cnt = collections.Counter()
def hook(fr, ev, arg):
    if ev == 'call' and fr.f_code in codes: cnt[codes[fr.f_code]] += 1
sys.setprofile(hook); out = p1.degenerate(np.random.default_rng(p1.SEED)); sys.setprofile(None)
print("degenerate trials", len(out), "all refused", all(c['refused'] for c in out), dict(cnt))
# refusal reasons
for c in out: print("  ", c['case'], c['verdict'][:70])
# 2. historical: which power functions ran
cnt.clear(); sys.setprofile(hook); h = p1.historical(np.random.default_rng(p1.SEED)); sys.setprofile(None)
print("historical calls", dict(cnt), [(c['case'], c['flagged']) for c in h])
# 3. order_stat_bar influence: replace with garbage output
orig = pw.order_stat_bar
pw.order_stat_bar = lambda *a, **k: {"corrected_bar": 12345.0}
h2 = p1.historical(np.random.default_rng(p1.SEED))
print("with garbage order_stat_bar flags", [(c['case'], c['flagged']) for c in h2])
pw.order_stat_bar = orig
# does the scored G1 metric come from the traced run? compare committed historical_caught
comm = json.load(open(R.HERE / 'p1_result.json'))
print("committed historical_caught", comm['historical_caught'], "fresh", sum(c['flagged'] is True for c in h))
