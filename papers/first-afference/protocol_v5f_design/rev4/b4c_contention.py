# How often an opener waits in _await_clearers, and for how long, with no hooks: 4 threads open and close sections of
# one tracer in a tight loop for 3 s at a 1 us switch interval (so closes that clear race opens constantly), and the
# same with a pure-Python profile function on every thread (threading.setprofile_all_threads), which runs Python
# code inside every _unwind_off. Counts every section, every wait, the total and the longest wait.
import sys, threading, time
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4 as mech
def t(): raise KeyError
def body():
    try: t()
    except KeyError: pass
waits = []
orig = mech._await_clearers
def timed():
    t0 = time.perf_counter(); orig(); waits.append(time.perf_counter() - t0)
mech._await_clearers = timed
def run(prof):
    waits.clear(); stop = [False]; n = [0] * 4
    sys.setswitchinterval(1e-6)
    if prof: threading.setprofile_all_threads(lambda f, e, a: None)
    with mech.Tracer(t) as tr:
        def w(i):
            while not stop[0]: tr.run('S', body); n[i] += 1
        ths = [threading.Thread(target=w, args=(i,)) for i in range(4)]
        for th in ths: th.start()
        time.sleep(3); stop[0] = True
        for th in ths: th.join()
    if prof: threading.setprofile_all_threads(None)
    sys.setswitchinterval(0.005)
    r = tr.result()
    print(sys.version.split()[0], 'profiler on every thread: %-5s sections %d, counted %d, MONITOR_LOST %s | waits %d (%.2f%% of opens), total %.1f ms, longest %.3f ms'
          % (prof, sum(n), r['calls'].get('S', {}).get('t', 0), r['MONITOR_LOST'], len(waits), 100.0 * len(waits) / max(1, sum(n)), 1e3 * sum(waits), 1e3 * max(waits or [0])))
run(False); run(True)
