# M6: while a self-trace has minted a machinery function (here `_open_like`), which code object must
# _v5_faultpoints() return, and does an injector filtered by thread ident fault only the case thread?
import sys, threading
sys.path.insert(0, '.')
import mech2 as mech
M = sys.monitoring; E = M.events
def _open_like(x): return x + 1                     # stands for a machinery function the self-trace declares
import_time_code = _open_like.__code__
hits = {'case': 0, 'other': 0}
case_tid = [None]
def inj(code, off):
    pass
    if threading.get_ident() == case_tid[0]: hits['case'] += 1
    else: hits['other'] += 1
M.use_tool_id(5, 'injector'); M.register_callback(5, E.INSTRUCTION, inj)
def run(code_for_injector, filtered):
    hits['case'] = hits['other'] = 0
    M.set_local_events(5, code_for_injector, E.INSTRUCTION)
    bar = threading.Barrier(2); armed = threading.Event()
    def other():
        bar.wait(); armed.wait()
        for _ in range(100): _open_like(1)          # the self-trace's own calls on another, live thread
        bar.wait()
    def case():
        bar.wait(); armed.wait()
        for _ in range(100): _open_like(1)
        bar.wait()
    tc = threading.Thread(target=case); to = threading.Thread(target=other)
    tc.start(); to.start()
    case_tid[0] = tc.ident                          # read while the case thread is alive (idents are reused)
    armed.set()
    tc.join(); to.join(); case_tid[0] = None
    M.set_local_events(5, code_for_injector, 0)
    return dict(hits) if not filtered else {'case': hits['case'], 'other (filtered out)': hits['other']}
with mech.Tracer(_open_like) as selftrace:          # the self-trace mints the machinery function
    print(sys.version.split()[0], 'code captured at import :', run(import_time_code, False))
    print(sys.version.split()[0], 'fn.__code__ at call time:', run(_open_like.__code__, True), '(injector faults only case-thread events)')
