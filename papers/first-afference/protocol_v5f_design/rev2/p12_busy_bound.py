# M12/N6: boundary rows on both sides of the 10 s busy bound, with the waiter synchronised to the block.
# A model of M2's wait (poll every 0.2 ms, give up after _BUSY_SECONDS). The owner's block is measured from the
# moment the waiter starts: the owner waits for the waiter's "started" event, then holds for D more seconds.
# X138: D = 11 -> the waiter must get MACHINERY_BUSY. X138b: D = 7 -> the waiter must succeed, after waiting >= 6 s (7, not 5, so that x0.5 = 5 s is killed).
# Mutants of the float constant (SM2 O7b: x0.5 and x2, and the critic's 0.5 s) must each fail one of the two.
import sys, threading, time
def run(bound, D):
    held = threading.Event(); started = threading.Event(); release = [False]
    def owner():
        held.set(); started.wait(); time.sleep(D); release[0] = True
    t = threading.Thread(target=owner); t.start(); held.wait()
    t0 = time.monotonic(); started.set()
    while not release[0]:
        if time.monotonic() - t0 > bound: e = time.monotonic() - t0; t.join(); return 'MACHINERY_BUSY', e
        time.sleep(0.0002)
    e = time.monotonic() - t0; t.join(); return 'acquired', e
ver = sys.version.split()[0]
for bound, label in ((10.0, 'spec 10.0'), (0.5, 'mutant 0.5'), (5.0, 'mutant x0.5'), (20.0, 'mutant x2')):
    a = run(bound, 11); b = run(bound, 7)
    ok_a = a[0] == 'MACHINERY_BUSY'; ok_b = b[0] == 'acquired' and b[1] >= 6
    print(ver, '%-11s X138 (11 s): %s after %.1f s [%s]; X138b (7 s): %s after %.1f s [%s]' % (
        label, a[0], a[1], 'pass' if ok_a else 'FAIL', b[0], b[1], 'pass' if ok_b else 'FAIL'))
