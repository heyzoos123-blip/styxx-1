"""round4/lifecycle/r1/f08_reentry_race.py, rewritten: one tracer object shared by two worker threads that enter
it together (a barrier), the declared module dropped from sys.modules first so the enter's import really runs;
inside, each runs one section and waits for the other (a 5 s barrier). 20 attempts (the repro's up to 200, which
stopped at the first double entry); per attempt the two outcomes (entered or the refusal code), and for an attempt
where both entered, the record. _v5_state() after."""
import collections, importlib, sys, threading


def main(api):
    api.fixture("rp_lc_f08", "def a(x=0): return x + 1\ndef b(x=0): return x + 2\ndef c(x=0): return x + 3\ndef d(x=0): return x + 4\n")
    e = api.exp({"G": [f"rp_lc_f08:{n}" for n in "abcd"]})
    seen, both = collections.Counter(), []
    for _ in range(20):
        sys.modules.pop("rp_lc_f08", None)
        importlib.invalidate_caches()
        COV = api.coverage_trace(e)
        start, inside, out = threading.Barrier(2), threading.Barrier(2, timeout=5), {}

        def worker(i):
            start.wait()
            try:
                with COV:
                    m = sys.modules["rp_lc_f08"]
                    COV.run("G", lambda: (m.a(), m.b(), m.c(), m.d()) and None)
                    try:
                        inside.wait()
                    except threading.BrokenBarrierError:
                        pass
                out[i] = "entered"
            except BaseException as ex:                # noqa: BLE001
                msg = str(ex)
                out[i] = msg[4:msg.index("]")] if msg.startswith("[V5:") else type(ex).__name__
                try:
                    inside.abort()
                except Exception:                      # noqa: BLE001
                    pass
        ths = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
        [t.start() for t in ths]
        [t.join(30) for t in ths]
        key = "|".join(sorted(out.values()))
        seen[key] += 1
        if key == "entered|entered":
            both.append(api.record(COV))
    return {"attempts": dict(sorted(seen.items())), "double_entries": both[:3], "state": api.state()}
