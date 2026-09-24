# A library that lazily starts a long-lived daemon thread the first time it is used (tqdm's
# TMonitor; similarly logging.handlers.QueueListener, telemetry/heartbeat threads) — the harness
# does not own the thread and cannot join it.
from rtlib import *
import fx_simple, sys
def with_tqdm():
    from tqdm import tqdm
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"):
            for _ in tqdm(range(3), file=sys.stderr, mininterval=0): fx_simple.f()
    return score(e, cov.record())
attempt("L1 tqdm progress bar first used inside a section", with_tqdm)
