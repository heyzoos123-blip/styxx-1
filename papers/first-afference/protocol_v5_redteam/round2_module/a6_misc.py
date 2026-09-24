from rtlib import *
import fx_simple as fs, fx2_rec, threading, sys, asyncio, contextvars, time

def recursion_refusal():
    # gate: the parser must refuse pathologically deep input (RecursionError is the refusal)
    e = exp(spec(G={"exercises": ["fx2_rec:parse"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"):
            fx2_rec.parse("x" * 10)
            try: fx2_rec.parse("x" * 100000)
            except RecursionError: pass
            fx2_rec.parse("x" * 10)
    return score(e, cov.record())
attempt("A6a RecursionError caught inside a section", recursion_refusal)

def same_name_concurrent():
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    errs = []; bar = threading.Barrier(2)
    with coverage_trace(e) as cov:
        def shard(k):
            try:
                with cov.section("G"):
                    fs.f()
                    h = threading.Thread(target=time.sleep, args=(0.3 if k else 0.0,)); h.start()
                    bar.wait()
                    if k == 0: pass            # shard 0 closes while shard 1's helper still runs
                    else: h.join()
                    if k == 0: h.join()
            except Exception as ex: errs.append(f"shard{k}: {str(ex)[:90]}")
        ts = [threading.Thread(target=shard, args=(k,)) for k in (0, 1)]
        [t.start() for t in ts]; [t.join() for t in ts]
    return f"errs={errs}"
attempt("A6b same section in two shards; each joins its own helper", same_name_concurrent)

def ctx_mismatch():
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    with coverage_trace(e) as cov:
        async def main():
            cm = cov.section("G")
            await asyncio.create_task(asyncio.to_thread(lambda: None)) if False else None
            async def opener(): cm.__enter__()
            await asyncio.create_task(opener())      # enter in one task
            fs.f()
            cm.__exit__(None, None, None)            # exit in another
        asyncio.run(main())
attempt("A6c section entered/exited in different contexts (ExitStack/fixture style)", ctx_mismatch)

def declared_thread_start():
    e = exp(spec(G={"exercises": ["threading:Thread.start"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"):
            t = threading.Thread(target=lambda: None); t.start(); t.join()
    return score(e, cov.record())
attempt("A6d declared target threading:Thread.start, really called", declared_thread_start)

def del_deadlock():
    e = exp(spec(G={"exercises": ["fx_simple:f"]}))
    class Res:
        def __del__(self): fs.f()
    import gc
    with coverage_trace(e) as cov:
        with cov.section("G"):
            fs.f()
            # a reference cycle whose finalizer calls a declared target
            a = Res(); a.self = a; del a
            # record() holds the lock while building dicts; force a gc there
            gc.set_threshold(1)
            try:
                r = cov.record()
            finally:
                gc.set_threshold(700, 10, 10)
    return "no deadlock"
import signal
signal.signal(signal.SIGALRM, lambda *a: (_ for _ in ()).throw(TimeoutError("DEADLOCK: alarm fired")))
signal.alarm(5)
attempt("A6e finalizer calling a target while tracer lock held", del_deadlock)
signal.alarm(0)
