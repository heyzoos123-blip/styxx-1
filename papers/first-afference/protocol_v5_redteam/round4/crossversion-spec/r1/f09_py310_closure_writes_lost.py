"""F09: on CPython 3.10 the tracer corrupts the traced program: closure (cell) variables written by
another thread are silently reverted while a section is open.

Cause: on 3.10 every Python-level profile callback is wrapped by sysmodule.c call_trampoline in
PyFrame_FastToLocalsWithError(frame) ... PyFrame_LocalsToFast(frame, 1), which writes the frame's
locals snapshot back into its cells (bpo-30744). _hook is Python code, so the GIL can switch while
it runs; a cell written by a worker thread in that window is overwritten with the stale snapshot
when the callback returns. 3.11+ only write back when f_locals was materialised, and _hook never
reads f_locals, so 3.11-3.13 are unaffected. The same harness with no section open loses nothing.

Two shapes, both ordinary harness code: (1) a worker thread counting into a `nonlocal` counter
while the section thread polls it -- updates are lost; (2) a worker setting a `nonlocal done =
True` flag once, and the section thread waiting on it -- the flag can be reverted to False and the
harness waits forever (bounded here by a deadline so the script terminates).
Spec: the BLOCKER class includes "a crash/corruption of the user's program in legitimate use";
Finding closure "R3 nit: f_locals cost | CLOSED_S | f_locals is never read"; Versions: "Executed on
3.10-3.13, with identical batteries apart from cProfile".
Run: PYTHONPATH=/home/user/styxx-1 python f09_py310_closure_writes_lost.py
"""
import json, subprocess, sys, tempfile, threading, time
from pathlib import Path

tmp = Path(tempfile.mkdtemp(prefix="rt4xv_f09_"))
modname = "_rt4xv_f09_mod"
(tmp / f"{modname}.py").write_text("def poll(x=0):\n    return x\n")
sys.path.insert(0, str(tmp))
repo = tmp / "repo"; repo.mkdir()
spec = {"gates": {"G": {"metric": "m", "op": ">=", "value": 0.5, "exercises": [f"{modname}:poll"]}},
        "outcomes": [{"when": {"G": True}, "verdict": "PASS"}, {"when": {}, "verdict": "FAIL"}],
        "smoke_verdict": "S"}
p = repo / "PREREG_f09.md"
p.write_text("# f09\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "-c", "commit.gpgsign=false", "commit", "-qm", "c"]):
    subprocess.run(cmd, cwd=repo, check=True)

from styxx.protocol import Experiment, coverage_trace
import importlib
mod = importlib.import_module(modname)
exp = Experiment(p)
import os
if os.environ.get("RT4_DEFAULT_SWITCH") != "1":
    sys.setswitchinterval(1e-6)    # a busy machine; makes the window easy to hit in a short run

def counting_harness():
    counter = 0
    N = 300_000
    def worker():
        nonlocal counter
        for _ in range(N):
            counter += 1
    t = threading.Thread(target=worker); t.start()
    seen = []
    while t.is_alive():
        seen.append(len(seen))                      # ordinary builtin calls in the waiting frame
        mod.poll()
    t.join()
    return N - counter                              # lost updates

def flag_harness(trials=300, deadline=0.05):
    stuck = 0
    for _ in range(trials):
        done = False
        spins = []
        def worker():
            nonlocal done
            while len(spins) < 50:                   # wait until the harness is in its wait loop
                pass
            done = True                              # set exactly once, then the worker exits
        t = threading.Thread(target=worker); t.start()
        end = time.monotonic() + deadline
        while not done and time.monotonic() < end:  # a spin-wait on the flag
            spins.append(len(spins))
        mod.poll()
        t.join()
        if not done:                                 # the worker DID set it: the write was reverted
            stuck += 1
    return stuck

ver = sys.version.split()[0]
plain_lost = counting_harness()
with coverage_trace(exp) as cov:
    traced_lost = cov.run("G", counting_harness)
    traced_stuck = cov.run("G", flag_harness)
plain_stuck = flag_harness()
verdict = exp.score({"m": 1.0, "coverage_trace": cov.record()}).verdict
print(f"[{ver}] lost counter updates: untraced {plain_lost}, in a section {traced_lost}; "
      f"flag trials that saw done revert to False: untraced {plain_stuck}, in a section {traced_stuck}; verdict {verdict}")
if (traced_lost > 0 or traced_stuck > 0) and plain_lost == 0 and plain_stuck == 0:
    print(f"FINDING-REPRODUCED: on {ver} an open section silently reverts closure variables written by another "
          f"thread ({traced_lost} lost updates; {traced_stuck} reverted done-flags); untraced runs lose none")
else:
    print(f"no finding: on {ver} the section did not change the program's closure writes")
