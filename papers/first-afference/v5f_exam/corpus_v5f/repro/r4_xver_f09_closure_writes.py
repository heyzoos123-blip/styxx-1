"""round4/crossversion-spec/r1/f09_py310_closure_writes_lost.py, rewritten: with the switch interval at 1e-6, (1)
a worker thread counting 300 000 times into a nonlocal counter while the section thread polls the declared target
(lost updates), (2) a worker setting a nonlocal done flag once while the section thread spin-waits on it with a
0.05 s deadline, 50 trials (the repro's 300); both untraced and inside a section. The switch interval is restored
after."""
import sys, threading, time


def main(api):
    mod = api.fixture("rp_xv_f09_mod", "def poll(x=0):\n    return x\n")
    e = api.exp({"G": ["rp_xv_f09_mod:poll"]})

    def counting_harness():
        counter = 0
        N = 300_000

        def worker():
            nonlocal counter
            for _ in range(N):
                counter += 1
        t = threading.Thread(target=worker)
        t.start()
        seen = []
        while t.is_alive():
            seen.append(len(seen))
            mod.poll()
        t.join()
        return N - counter

    def flag_harness(trials=50, deadline=0.05):
        stuck = 0
        for _ in range(trials):
            done = False
            spins = []

            def worker():
                nonlocal done
                while len(spins) < 50:
                    pass
                done = True
            t = threading.Thread(target=worker)
            t.start()
            end = time.monotonic() + deadline
            while not done and time.monotonic() < end:
                spins.append(len(spins))
            mod.poll()
            t.join()
            if not done:
                stuck += 1
        return stuck
    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        out = {"untraced_lost": counting_harness()}
        out["traced"] = api.trace(e, lambda c: c.run("G", counting_harness), lambda c: c.run("G", flag_harness))
        out["untraced_stuck"] = flag_harness()
    finally:
        sys.setswitchinterval(old)
    return out
