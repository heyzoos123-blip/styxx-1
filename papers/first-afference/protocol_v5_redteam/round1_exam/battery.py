import sys, json, tempfile
from pathlib import Path
sys.argv=['x']
sys.path.insert(0,'papers/first-afference')
import run_protocol_v5 as R
fixdir = Path(tempfile.mkdtemp(prefix="v5fix_"))
(fixdir / f"{R.FIX}.py").write_text(R.FIXTURE); sys.path.insert(0, str(fixdir)); __import__(R.FIX)
out = {}
for fn in (R.violations, R.valids):
    try:
        for k, (r, s) in fn().items(): out[k] = [r, s[:110]]
    except BaseException as e:
        out[fn.__name__ + "_CRASHED"] = [None, f"{type(e).__name__}: {str(e)[:100]}"]
print(json.dumps(out))
