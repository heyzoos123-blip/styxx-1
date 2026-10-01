"""round3_module/t09_library_threads.py, rewritten: a library that lazily starts a long-lived daemon monitor
thread the first time it is used inside a section (the repro used tqdm's TMonitor; tqdm is not a pinned
dependency, so the library here is a fixture with the same shape: a daemon thread started on first use that the
harness neither owns nor joins)."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r3m_fx import SIMPLE

LIB = '''
import threading
_monitor = None
_stop = threading.Event()
def _watch():
    while not _stop.wait(0.01):
        pass
def progress(it):
    global _monitor
    if _monitor is None:
        _monitor = threading.Thread(target=_watch, daemon=True)
        _monitor.start()
    for x in it:
        yield x
'''


def main(api):
    fs, lib = api.fixture("rp_fx_simple", SIMPLE), api.fixture("rp_fx3_lib", LIB)

    def body():
        for _ in lib.progress(range(3)):
            fs.f()
    out = {"L1": api.trace(api.exp({"G": ["rp_fx_simple:f"]}), lambda c: c.run("G", body))}
    lib._stop.set()
    lib._monitor.join(10)
    return out
