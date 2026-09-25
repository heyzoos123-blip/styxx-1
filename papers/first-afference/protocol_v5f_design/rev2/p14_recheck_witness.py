# X143 (M4 witness for the opener's re-check): T1's _open is paused after its first _unwind_on() and before its
# anchor commit; meanwhile T2 closes the last other section (its _unwind_off clears PY_UNWIND and re-checks an
# empty _ANCHORS). T1 then commits and runs a target that raises inside its body. With the re-check, the call is
# counted; without it (mutant: T1's second _unwind_on() skipped), PY_UNWIND is off for T1's section.
import sys, threading
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech2 as mech
def t(): raise KeyError
def body():
    try: t()
    except KeyError: pass
def run(recheck):
    orig_on = mech._unwind_on
    n1 = [0]; at_first = threading.Event(); resume = threading.Event()
    def on():
        if threading.current_thread().name != 'T1': return orig_on()
        n1[0] += 1
        if n1[0] == 1:
            orig_on(); at_first.set(); resume.wait(5)  # pause after T1's first set, before its commit
        elif n1[0] == 2 and recheck:
            orig_on()                                  # the re-check after the commit (deleted in the mutant)
    mech._unwind_on = on
    with mech.Tracer(t) as tr:
        t2_open = threading.Event(); t2_close = threading.Event()
        def T2():
            def sec(): t2_open.set(); t2_close.wait(5)
            tr.run('B', sec)
        th2 = threading.Thread(target=T2, name='T2'); th2.start(); t2_open.wait(5)
        th1 = threading.Thread(target=lambda: tr.run('A', body), name='T1'); th1.start()
        at_first.wait(5)
        t2_close.set(); th2.join(5)                    # T2's close: pop, clear, re-check (T1 not committed yet)
        resume.set(); th1.join(5)
    mech._unwind_on = orig_on
    return tr.result()['calls']
print(sys.version.split()[0], 'X143 spec (re-check after commit):', run(True), '| mutant (no re-check):', run(False))
