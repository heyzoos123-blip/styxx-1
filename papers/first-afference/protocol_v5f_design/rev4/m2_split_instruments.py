# MF1: an instrument that runs Python code between _unwind_off's _ANCHORS test and its clear, on the closing thread,
# against revision 3 (one-line test-and-clear, no announcement) and revision 4 (announce, test, clear, withdraw; the
# opener waits for announced clearers before it sets the event and arms). The critic's a2, made deterministic for
# both revisions by a handshake and extended to every instrument the critic's a1 found to split the expression:
#   T2 closes B, the last anchor. The instrument blocks T2 after its test found _ANCHORS empty, before its clear
#   ("between"), until T1 either has started A's body or has entered _await_clearers (revision 4's wait). Then, after
#   T2's clear ("after"), the instrument blocks T2 again only if A's body has already started, until the body has
#   raised t. A's body starts, releases T2, waits until T2 has cleared, then calls t (raises inside, caught).
# Revision 3: T1 never waits, so its body starts before T2's clear and t raises with the event clear: lost.
# Revision 4: T1 waits in _await_clearers until T2 withdraws, then sets the event; t is counted.
# No timeouts decide anything; every wait has a 5 s watchdog that only reports.
import sys, threading, dis
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech4 as mech
M = sys.monitoring; E = M.events
def t(): raise KeyError
def g(): return 1
OFF = (mech._unwind_off.__code__, mech._unwind_off_rev4.__code__)
def clear_call_offsets(code):                           # every set_events CALL offset, and the offset after it
    ins = list(dis.get_instructions(code)); calls, nexts = set(), set()
    for i, x in enumerate(ins):
        if x.argval == 'set_events':
            for j in range(i, len(ins)):
                if ins[j].opname.startswith('CALL'):
                    calls.add(ins[j].offset); nexts.add(ins[j + 1].offset); break
    return calls, nexts
POINTS = {c: clear_call_offsets(c) for c in OFF}
def scenario(rev4, instrument):
    mech.REV4[0] = rev4
    ev = {k: threading.Event() for k in ('opened', 'close', 'at_between', 'release', 'cleared', 'body', 't_done')}
    watchdog = []
    def wait(e, name):
        if not ev[e].wait(5): watchdog.append(name)
    st = {'between': False, 'after': False}
    T2id = {}
    def between():
        if st['between']: return
        st['between'] = True; ev['at_between'].set(); wait('release', 'release')
    def after():
        if st['after'] or not st['between']: return
        st['after'] = True; ev['cleared'].set()
        if ev['body'].is_set(): wait('t_done', 't_done')
    # instruments, each confined to T2 and to _unwind_off's code
    def prof(frame, event, arg):
        if frame.f_code in OFF and arg is M.set_events:
            if event == 'c_call': between()
            elif event == 'c_return': after()
    def trace(frame, event, arg):
        if frame.f_code in OFF:
            frame.f_trace_opcodes = True
            if event == 'opcode':
                b, a = POINTS[frame.f_code]
                if frame.f_lasti in b: between()
                elif frame.f_lasti in a: after()
            return trace
        return None
    def mon_call(code, offset, callable, arg0):
        if threading.get_ident() == T2id.get('t') and callable is M.set_events: between()
    def mon_cret(code, offset, callable, arg0):
        if threading.get_ident() == T2id.get('t') and callable is M.set_events: after()
    def mon_ins(code, offset):
        if threading.get_ident() != T2id.get('t'): return
        b, a = POINTS[code]
        if offset in b: between()
        elif offset in a: after()
    def arm_mon():
        M.use_tool_id(2, 'probe')
        if instrument == 'monitoring CALL + C_RETURN':
            M.register_callback(2, E.CALL, mon_call); M.register_callback(2, E.C_RETURN, mon_cret)
            for c in OFF: M.set_local_events(2, c, E.CALL | E.C_RETURN | E.C_RAISE)
        else:
            M.register_callback(2, E.INSTRUCTION, mon_ins)
            for c in OFF: M.set_local_events(2, c, E.INSTRUCTION)
    def disarm_mon():
        for c in OFF: M.set_local_events(2, c, 0)
        for e_ in (E.CALL, E.C_RETURN, E.C_RAISE, E.INSTRUCTION): M.register_callback(2, e_, None)
        M.free_tool_id(2)
    def hook(p):                                          # revision 4's wait, seen on T1: release T2
        if p == 'wait:enter' and threading.current_thread().name == 'T1': ev['release'].set()
    out = {}
    with mech.Tracer(t, g) as tr:
        def b():
            ev['opened'].set(); wait('close', 'close')
            T2id['t'] = threading.get_ident()
            if instrument == 'sys.setprofile (pure Python)': sys.setprofile(prof)
            elif instrument == 'sys.settrace + f_trace_opcodes':
                def prime(frame, event, arg):             # 3.12.3 applies f_trace_opcodes set at 'call' only from the
                    if frame.f_code in OFF: frame.f_trace_opcodes = True   # next execution of the code, so prime it
                    return prime
                sys.settrace(prime); mech._unwind_off_rev4() if rev4 else mech._unwind_off(); sys.settrace(None)
                sys.settrace(trace)
        def t2():
            try: tr.run('B', b)
            finally: sys.setprofile(None); sys.settrace(None)
        def body():
            ev['body'].set(); ev['release'].set(); wait('cleared', 'cleared')
            try: t()
            except KeyError: pass
            ev['t_done'].set()
        th2 = threading.Thread(target=t2, name='T2'); th2.start(); wait('opened', 'opened')
        if instrument.startswith('monitoring'): arm_mon()
        mech._HOOK[0] = hook
        ev['close'].set(); wait('at_between', 'at_between')
        th1 = threading.Thread(target=lambda: out.setdefault('r', tr.run('A', body)), name='T1'); th1.start()
        th1.join(10); th2.join(10); mech._HOOK[0] = None
        if instrument.startswith('monitoring'): disarm_mon()
    r = tr.result(); s = mech.state()
    order = 'body started before T2 cleared' if ev['body'].is_set() and st['after'] and not watchdog and out else ''
    print(sys.version.split()[0], 'rev %d  %-32s A %-10s MONITOR_LOST %-5s | after exit anchors %d events %d clearing %d%s'
          % (4 if rev4 else 3, instrument, r['calls'].get('A'), r['MONITOR_LOST'], s['anchors'], s['global_events'], s['clearing'],
             (' | watchdog: ' + ','.join(watchdog)) if watchdog else ''))
for inst in ('sys.setprofile (pure Python)', 'sys.settrace + f_trace_opcodes', 'monitoring CALL + C_RETURN', 'monitoring INSTRUCTION'):
    for rev4 in (False, True):
        scenario(rev4, inst)
