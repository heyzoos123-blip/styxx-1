# The one-call premise vs sys.monitoring.register_callback: CPython raises the audit event
# 'sys.monitoring.register_callback' inside register_callback, i.e. INSIDE _register's one-call step,
# once per callback (5 times), after the name gate was evaluated.  A Python audit hook therefore runs inside
# the "atomic" step: it can switch threads, and it can raise part-way (partial registration).
import sys, threading, time
sys.path.insert(0, '/home/user/styxx-1/papers/first-afference/protocol_v5f_design/rev5')
import mech5 as mech
M = sys.monitoring; E = M.events
T = mech.TOOL[0]
def foreign_cb(*a): pass
res = {}

# ---- (1) thread switch inside the step: another thread frees styxx's id and a foreign tool takes it ----
go = threading.Event(); done = threading.Event(); ARM = [False]; hits = [0]
def hook(ev, args):
    if ev == 'sys.monitoring.register_callback' and ARM[0]:
        hits[0] += 1
        if hits[0] == 2:              # second callback of the five; the gate was read at the first
            go.set(); done.wait(2)    # blocks -> releases the GIL: a real thread switch inside the "one call"
sys.addaudithook(hook)
def foreign():
    go.wait(5)
    M.free_tool_id(T); M.use_tool_id(T, 'foreign-profiler')
    for ev in (E.PY_START, E.PY_RETURN, E.PY_UNWIND): M.register_callback(T, ev, foreign_cb)
    done.set()
mech.reset()
th = threading.Thread(target=foreign); th.start()
ARM[0] = True
prev = mech._register_named(T)
ARM[0] = False; th.join()
cur = {n: M.register_callback(T, getattr(E, n), None) for n in ('PY_START','PY_RETURN','PY_UNWIND')}
for n, c in cur.items(): M.register_callback(T, getattr(E, n), c)
res['1_thread_switch'] = dict(owner_now=M.get_tool(T),
    foreign_callbacks_overwritten_by_styxx={n: getattr(c, '__name__', c) for n, c in cur.items()},
    audit_hook_calls_inside_one_call=hits[0])
for e in mech._EVS5: M.register_callback(T, e, None)
M.free_tool_id(T)

# ---- (2) a raising audit hook (a sandbox that denies monitoring registration) -> partial registration ----
hits[0] = 0
def deny(ev, args):
    if ev == 'sys.monitoring.register_callback' and ARM2[0]:
        hits[0] += 1
        if hits[0] == 3: raise RuntimeError('denied by sandbox')
ARM2 = [False]; sys.addaudithook(deny)
M.use_tool_id(T, mech.NAME)
for e in mech._EVS5: M.register_callback(T, e, None)
ARM2[0] = True
try:
    mech._register_named(T); out = 'returned'
except RuntimeError as e: out = 'raised ' + str(e)
ARM2[0] = False
regd = {}
for e, f in mech.CALLBACKS:
    c = M.register_callback(T, e, None); M.register_callback(T, e, c); regd[e] = c is f
res['2_raising_hook'] = dict(step=out, registered_per_event=regd)
print(sys.version.split()[0], res)
