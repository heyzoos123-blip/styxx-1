from rtlib import *
import fx3_clone as c, fx3_wraps as w
# (a) section exits by exception: every close check (SHARED_CODE recount, THREAD_OUTLIVES,
#     HOOK_FAILED, PROFILER_REPLACED) is skipped. Clone alive at close -> stated limit says SHARED_CODE.
def a():
    c.REGISTRY.clear()
    e = exp(spec(G={"exercises": ["fx3_clone:target"]}))
    res = {"m": 1.0}
    with coverage_trace(e) as cov:
        try:
            with cov.section("G"):
                v = c.make_variant(); v(1)          # target itself never called
                raise TimeoutError("battery item timed out")   # harness tolerates a timeout
        except TimeoutError:
            pass
        print("   clone alive at close:", len(c.REGISTRY), " close_refusals:", cov.record()["close_refusals"])
    return score(e, cov.record())
attempt("T02a clone alive at close, section exited by exception", a)
# (b) per-item sections with a generic try/except (a common battery shape): close refusal swallowed,
#     record() carries it, score() ignores close_refusals.
def b():
    c.REGISTRY.clear()
    e = exp(spec(G={"exercises": ["fx3_clone:target"]}))
    errors = []
    with coverage_trace(e) as cov:
        for item in range(3):
            try:
                with cov.section("G"):
                    c.make_variant()(item)
            except Exception as ex:
                errors.append(str(ex)[:40])
    print("   errors:", errors)
    r = cov.record(); print("   close_refusals in record:", len(r["close_refusals"]))
    return score(e, r)
attempt("T02b close refusal swallowed by a per-item try/except", b)
# (c) R2-D2 at close (the repair's only defence for runtime wraps siblings) swallowed the same way
def cc():
    e = exp(spec(G={"exercises": ["fx3_wraps:public"]}))
    keep = []
    with coverage_trace(e) as cov:
        try:
            with cov.section("G"):
                h = w.retrying(w._core); keep.append(h); h(1)     # alive wraps sibling
        except Exception as ex:
            print("   swallowed:", str(ex)[:60])
    return score(e, cov.record())
attempt("T02c runtime wraps sibling alive at close, refusal swallowed", cc)
# (d) THREAD_OUTLIVES skipped on exception exit, and the late thread's calls then land in a later
#     re-opening of the same section name
import threading, time, fx_simple
def d():
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    with coverage_trace(e) as cov:
        try:
            with cov.section("G"):
                th = threading.Thread(target=lambda: (time.sleep(0.2), fx_simple.f())); th.start()
                raise RuntimeError("abort item")
        except RuntimeError:
            pass
        print("   thread alive after close:", th.is_alive(), "close_refusals:", cov.record()["close_refusals"])
        with cov.section("G"):
            time.sleep(0.4)      # this item calls nothing
        th.join()
    return score(e, cov.record())
attempt("T02d thread outlives an exception-exited section; its call credited to a later G", d)
