"""round2_module/a6_misc.py and a6a_recursion_rootcause.py, rewritten: a a RecursionError caught inside a
section (the parser's refusal of deep input); b the same section run in two shards concurrently, each starting
and joining its own helper thread; d the declared target threading:Thread.start, really called; e a reference
cycle whose finalizer calls a declared target, collected (gc threshold 1) while record() runs; a6a a RecursionError
raised and caught with an entered tracer and no section, then the tracer exited. (Part c, a section entered and
exited in different contexts, is not applicable: v5f's sections are calls, cov.run, and cannot be split across
contexts; NOT_APPLICABLE.json. The repro's SIGALRM deadlock alarm is replaced by the corpus run's timeout.)"""
import gc, os, sys, threading
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r2m_fx import REC, SIMPLE


def main(api):
    fs, rec = api.fixture("rp_fx_simple", SIMPLE), api.fixture("rp_fx2_rec", REC)
    out = {}

    def deep():
        rec.parse("x" * 10)
        try:
            rec.parse("x" * 100000)
        except RecursionError:
            pass
        return rec.parse("x" * 10)
    out["a_recursion_in_section"] = api.trace(api.exp({"G": ["rp_fx2_rec:parse"]}), lambda c: c.run("G", deep))
    errs = []

    def shards(c):
        bar = threading.Barrier(2)

        def shard(k):
            try:
                def body():
                    fs.f()
                    h = threading.Thread(target=lambda: None)
                    h.start()
                    bar.wait(10)
                    h.join()
                c.run("G", body)
            except BaseException as ex:                # noqa: BLE001
                errs.append(type(ex).__name__)
        ts = [threading.Thread(target=shard, args=(k,)) for k in (0, 1)]
        [t.start() for t in ts]
        [t.join(10) for t in ts]
    out["b_same_section_two_shards"] = api.trace(api.exp({"G": ["rp_fx_simple:f"]}), shards)
    out["b_errors"] = sorted(errs)

    def ts():
        t = threading.Thread(target=lambda: None)
        t.start()
        t.join()
    out["d_declared_thread_start"] = api.trace(api.exp({"G": ["threading:Thread.start"]}), lambda c: c.run("G", ts))

    class Res:
        def __del__(self):
            fs.f()
    keep = []

    def e_body():
        fs.f()
        a = Res()
        a.self = a
        del a
    e = api.exp({"G": ["rp_fx_simple:f"]})
    res = api.trace(e, lambda c: c.run("G", e_body), keep=keep)
    old = gc.get_threshold()
    gc.set_threshold(1)
    try:
        res["record_under_threshold_1"] = api.record(keep[0])
    finally:
        gc.set_threshold(*old)
    gc.collect()
    out["e_finalizer_during_record"] = res
    cov = api.coverage_trace(api.exp({"G": ["rp_fx2_rec:parse"]}))
    r = {"enter": api.attempt(lambda: cov.__enter__() is cov)}
    try:
        rec.parse("x" * 100000)
        r["recursion"] = False
    except RecursionError:
        r["recursion"] = True
    r["getprofile_none"] = sys.getprofile() is None
    r["exit"] = api.attempt(lambda: bool(cov.__exit__(None, None, None)))
    r["record"] = api.record(cov)
    out["a6a_recursion_no_section"] = r
    return out
