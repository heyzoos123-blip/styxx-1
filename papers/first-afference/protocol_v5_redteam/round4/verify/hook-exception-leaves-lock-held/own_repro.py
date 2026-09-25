"""Independent repro: a SIGALRM Timeout (the exam's own H2 pattern) raised inside styxx's _hook
while the hook runs for the c_call of `_LOCK.__exit__` at the end of `with _LOCK:` in _open.
No styxx internals are reset or touched until cleanup. The timer is armed only around cov.run.
After each caught exception the main thread (outside any styxx frame) checks _LOCK._is_owned().

usage: PYTHONPATH=/home/user/styxx-1 python own_repro.py [timeout|kbi] [budget_s]
"""
import json
import random
import signal
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import traceback
from pathlib import Path

import styxx.protocol as P
from styxx.protocol import Experiment, coverage_trace

KIND = sys.argv[1] if len(sys.argv) > 1 else "timeout"
BUDGET = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0

td = Path(tempfile.mkdtemp(prefix="vf_lock_"))
(td / "vf_lock_mod.py").write_text(textwrap.dedent("""
    def work(x=0):
        return x + 1
"""), encoding="utf-8")
sys.path.insert(0, str(td))
import vf_lock_mod  # noqa: E402

spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5,
                        "exercises": ["vf_lock_mod:work"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "S"}
(td / "PREREG_vf.md").write_text("# vf\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
for c in (["git", "init", "-q"], ["git", "add", "-A"],
          ["git", "-c", "user.email=a@b", "-c", "user.name=a", "-c", "commit.gpgsign=false",
           "commit", "-qm", "c"]):
    subprocess.run(c, cwd=td, check=True)
exp = Experiment(td / "PREREG_vf.md")


class Timeout(Exception):
    pass


ARMED = [False]
EXC = Timeout if KIND == "timeout" else KeyboardInterrupt


def handler(signum, frame):
    if ARMED[0]:
        ARMED[0] = False
        raise EXC()


signal.signal(signal.SIGALRM, handler)
rnd = random.Random(7)
end = time.monotonic() + BUDGET
cycles = raised = 0
leak = None
with coverage_trace(exp) as cov:
    while time.monotonic() < end and leak is None:
        cycles += 1
        try:
            try:
                ARMED[0] = True
                signal.setitimer(signal.ITIMER_REAL, rnd.uniform(0.00001, 0.0003))
                cov.run("G", vf_lock_mod.work, 1)
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
                ARMED[0] = False
        except EXC as e:
            raised += 1
            if P._LOCK._is_owned():            # we are outside every styxx frame here
                leak = traceback.extract_tb(e.__traceback__)
        else:
            if P._LOCK._is_owned():
                leak = "owned after a clean cycle"

    print(f"python {sys.version.split()[0]} kind={KIND} cycles={cycles} raised={raised}")
    if leak is None:
        print("NOT REPRODUCED: _LOCK never left owned")
        sys.exit(0)
    frames = " <- ".join(f"{fr.name}:{fr.lineno}" for fr in reversed(leak[-4:])) \
        if not isinstance(leak, str) else leak
    print("LEAK: main thread owns _LOCK outside styxx; exception path:", frames)
    print("      lock:", repr(P._LOCK)[-28:], "| main-thread profiler:", sys.getprofile())

    # the spec's remedy for pools: each job opens its own section, cov.run in the worker
    done = threading.Event()

    def job():
        cov.run("G", vf_lock_mod.work, 2)
        done.set()

    w = threading.Thread(target=job, daemon=True)
    t0 = time.monotonic()
    w.start()
    w.join(3.0)
    print(f"worker cov.run finished within 3 s: {done.is_set()} (waited {time.monotonic()-t0:.1f} s)")
    if not done.is_set():
        fr = sys._current_frames()[w.ident]
        stk = traceback.extract_stack(fr)[-3:]
        print("      worker blocked at:", " <- ".join(f"{s.name}:{s.lineno}" for s in reversed(stk)))
        n = 0
        while P._LOCK._is_owned():             # cleanup only, so the script can end
            P._LOCK.release(); n += 1
        w.join(3.0)
        print(f"      after force-releasing {n} level(s): worker finished = {done.is_set()}")
