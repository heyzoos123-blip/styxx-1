# rev13 (GAP-59): why G_ATOM's parts A and E fail on ref_v5f.py under the exam author's atom_v5f.py, and what the
# text must fix. Reads (never writes) v5f_exam/atom_v5f.py, ref_v5f.py and the revision-5 prototype
# rev5/t1_onecall_atomic.py. Run: <venv3.12|venv3.13>/bin/python p_gap59.py
#   A1  the exam author's part-A clearing function (M7's _unwind_off form): its Python-level calls, and the events a
#       LOCAL CALL+C_RETURN+C_RAISE tool delivers inside it
#   A2  the revision-5 prototype's off_onecall (a third gate, on get_events): the same, and the prototype's own
#       GLOBAL-tool count, which includes the harness's calls after the step returned
#   E   part E's control under the exam author's harness and under the prototype's harness, with ablations; and the
#       one-call form, and the reference implementation's own _unwind_on/_unwind_off, under the prototype's harness
import dis, importlib.util, json, os, sys, threading, time, types
HERE = os.path.dirname(os.path.abspath(__file__))
EXAM = os.path.join(HERE, '..', '..', 'v5f_exam')
sys.argv = [os.path.join(EXAM, 'atom_v5f.py')]
spec = importlib.util.spec_from_file_location('atom_v5f', os.path.join(EXAM, 'atom_v5f.py'))
AT = importlib.util.module_from_spec(spec); spec.loader.exec_module(AT)
MON, EV = sys.monitoring, sys.monitoring.events
V = sys.version.split()[0]
AT.load()                                   # the implementation, bound by one enter and exit (the exam's way)
REF = AT.ref_pipelines()
P = AT.P

def calls_in(code):
    return sum(1 for i in dis.get_instructions(code) if i.opname in ('CALL', 'CALL_FUNCTION_EX', 'CALL_KW'))

def local_call_events(fn, arg_setup):
    """Events a local CALL+C_RETURN+C_RAISE tool on fn's code delivers during one undisturbed call."""
    n = [0]
    MON.use_tool_id(1, 'p59')
    for e in (EV.CALL, EV.C_RETURN, EV.C_RAISE):
        MON.register_callback(1, e, lambda *a: n.__setitem__(0, n[0] + 1))
    MON.set_local_events(1, fn.__code__, EV.CALL | EV.C_RETURN | EV.C_RAISE)
    fn(arg_setup())
    MON.set_local_events(1, fn.__code__, 0)
    for e in (EV.CALL, EV.C_RETURN, EV.C_RAISE): MON.register_callback(1, e, None)
    MON.free_tool_id(1)
    return n[0]

def a_key():
    AT.A.clear(); k = object(); AT.A[k] = 1; MON.set_events(AT.RTOOL, EV.PY_UNWIND); return k

out = {'version': V}
out['A1_exam_clear_one'] = {'python_level_calls': calls_in(REF['clear_one'].__code__),
                            'local_call_events': local_call_events(REF['clear_one'], a_key)}
# the revision-5 prototype
sp = importlib.util.spec_from_file_location('t1', os.path.join(HERE, '..', 'rev5', 't1_onecall_atomic.py'))
T1 = importlib.util.module_from_spec(sp); sp.loader.exec_module(T1)
T1.T = 0                                     # the prototype used id 4, the implementation's here; 1, 2 and 5 are taken too
def t1_key():
    T1.setup(); T1.A['closer'] = True; MON.set_events(T1.T, EV.PY_UNWIND); return 'closer'
out['A2_prototype_off_onecall'] = {'python_level_calls': calls_in(T1.off_onecall.__code__),
                                   'local_call_events': local_call_events(T1.off_onecall, t1_key)}
f = 0; k = 1
while True:                                  # the prototype's own count: a GLOBAL CALL+C_RETURN+C_RAISE tool
    fired, _ = T1.trial(T1.off_onecall, k, 'CALL+C_RETURN')
    if not fired: break
    f += 1; k += 1
out['A2_prototype_off_onecall']['prototype_global_tool_trials'] = f
MON.set_events(T1.T, 0); MON.free_tool_id(T1.T)

# ---------------- part E ----------------
def part_e(close, opener, sample, *, body_yield, after_close_yield, prof_wait, switch, floor, until_first, nthreads=4):
    ccode = close.__code__
    st = {'samples': 0, 'clear': 0, 'stop': False}
    lock = threading.Lock()
    def prof(frame, event, arg):
        if event == 'c_call' and frame.f_code is ccode:
            time.sleep(prof_wait)
    def worker():
        sys.setprofile(prof)
        s = c = 0
        while not st['stop']:
            key = opener()
            for _ in range(3 if body_yield else 4):
                s += 1; c += not sample()
                if body_yield: time.sleep(0)
            close(key)
            if after_close_yield: time.sleep(0)
            if s >= 64:
                with lock: st['samples'] += s; st['clear'] += c
                s = c = 0
        sys.setprofile(None)
        with lock: st['samples'] += s; st['clear'] += c
    old = sys.getswitchinterval()
    if switch: sys.setswitchinterval(switch)
    ths = [threading.Thread(target=worker) for _ in range(nthreads)]
    t0 = time.monotonic()
    for t in ths: t.start()
    while not (st['samples'] >= floor or (until_first and st['clear']) or time.monotonic() - t0 > 60): time.sleep(0.005)
    st['stop'] = True
    for t in ths: t.join()
    sys.setswitchinterval(old)
    return {'samples': st['samples'], 'clear': st['clear'], 'seconds': round(time.monotonic() - t0, 2)}

def ref_opener():
    k = object(); REF['open_one'](k, k); return k
ref_sample = lambda: bool(MON.get_events(AT.RTOOL) & EV.PY_UNWIND)
HARNESS = {
 'exam_author':           dict(body_yield=False, after_close_yield=False, prof_wait=1e-5, switch=None),
 'prototype':             dict(body_yield=True, after_close_yield=True, prof_wait=0, switch=1e-6),
 'prototype_no_switch':   dict(body_yield=True, after_close_yield=True, prof_wait=0, switch=None),
 'prototype_no_body_yield': dict(body_yield=False, after_close_yield=False, prof_wait=0, switch=1e-6),
 'exam_author_plus_body_yield': dict(body_yield=True, after_close_yield=True, prof_wait=1e-5, switch=None),
}
E = {}
for name, h in HARNESS.items():
    AT.A.clear(); MON.set_events(AT.RTOOL, 0)
    E['control/' + name] = part_e(REF['clear_two'], ref_opener, ref_sample, floor=50000, until_first=True, **h)
for name in ('exam_author', 'prototype'):
    AT.A.clear(); MON.set_events(AT.RTOOL, 0)
    E['one_call/' + name] = part_e(REF['clear_one'], ref_opener, ref_sample, floor=50000, until_first=False, **HARNESS[name])
# the implementation's own steps, through the G_ATOM interface, under the prototype's harness
FP = P._v5_faultpoints()
UON = types.FunctionType(FP['_unwind_on'], vars(P)); UOFF = types.FunctionType(FP['_unwind_off'], vars(P))
core = P._Core.__new__(P._Core); core.flags = {}
t = P._TOOL[0]
def impl_opener():
    o = P._Opening.__new__(P._Opening); o.core = core; o.armed = False; o.frame = object()
    P._ANCHORS[o.frame] = o; UON(o); o.armed = True; return o.frame
impl_sample = lambda: bool(MON.get_events(t) & EV.PY_UNWIND)
P._ANCHORS.clear(); MON.set_events(t, 0)
E['implementation_steps/prototype'] = part_e(UOFF, impl_opener, impl_sample, floor=50000, until_first=False, **HARNESS['prototype'])
E['implementation_steps/prototype']['UNWIND_LOST_flagged'] = 'UNWIND_LOST' in core.flags
E['implementation_steps/prototype']['anchors_left'] = len(P._ANCHORS)
P._ANCHORS.clear(); MON.set_events(t, 0)
out['E'] = E
print(json.dumps(out))
sys.stdout.flush(); os._exit(0)
