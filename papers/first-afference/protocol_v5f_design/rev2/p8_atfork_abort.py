# N5: the at-fork handler restores __code__ (an object.__setattr__ audit event). A raising audit hook aborts the
# handler; CPython ignores (prints) exceptions from at-fork handlers. rev 1 order: pid, guard, retire every mint
# (restore first), clear registries, clear global events. rev 2 order: guard, anchors, global events, per-mint
# pending/local events/registries, and the __code__ restores last; pass-through reads os.getpid(), not a cache.
# Reports what the child is left with, and the cost of os.getpid() against a cached read.
import sys, os, json, timeit
M = sys.monitoring; E = M.events
TOOL = 4
def f(): return 1
class Mint: pass
STATE = {}
def setup():
    M.use_tool_id(TOOL, 'model'); M.register_callback(TOOL, E.PY_UNWIND, lambda *a: None)
    m = Mint(); m.fn = f; m.original = f.__code__; m.code = f.__code__.replace(); m.pend = {1: 'x'}
    STATE.update(minted={id(m.code): m}, anchors={'frame': 1}, pid=[os.getpid()], orig_code=m.original)
    M.set_local_events(TOOL, m.code, E.PY_START); M.set_events(TOOL, E.PY_UNWIND); f.__code__ = m.code
def retire(m):
    if m.fn.__code__ is m.code: m.fn.__code__ = m.original      # audit event: may raise
    M.set_local_events(TOOL, m.code, 0); m.pend.clear()
def forget_rev1():
    STATE['pid'][0] = os.getpid()
    for m in list(STATE['minted'].values()): retire(m)
    STATE['minted'].clear(); STATE['anchors'].clear()
    M.set_events(TOOL, 0)
def forget_rev2():
    STATE['anchors'].clear()
    M.set_events(TOOL, 0)
    ms = list(STATE['minted'].values())
    for m in ms: M.set_local_events(TOOL, m.code, 0); m.pend.clear()
    STATE['minted'].clear()
    for m in ms:
        if m.fn.__code__ is m.code: m.fn.__code__ = m.original  # user code (audit hooks) runs last
def hook(event, args):
    if event == 'object.__setattr__' and len(args) > 1 and args[1] == '__code__' and os.getpid() != PARENT:
        raise RuntimeError('audit hook refuses __code__ writes in the child')
PARENT = os.getpid()
which = sys.argv[1]
setup()
os.register_at_fork(after_in_child=forget_rev1 if which == 'rev1' else forget_rev2)
sys.addaudithook(hook)
r, w = os.pipe()
pid = os.fork()
if pid == 0:
    os.close(r)
    st = {'pid_cache_stale': STATE['pid'][0] != os.getpid(), 'anchors': len(STATE['anchors']),
          'mints_registered': len(STATE['minted']), 'global_events': M.get_events(TOOL),
          'f_still_minted': f.__code__ is not STATE['orig_code']}
    os.write(w, json.dumps(st).encode()); os._exit(0)
os.close(w); data = os.read(r, 4096); os.waitpid(pid, 0)
print(sys.version.split()[0], which, 'child state after the aborted handler:', data.decode())
if which == 'rev2':
    cached = [os.getpid()]
    a = min(timeit.repeat(lambda: cached[0] != 0, number=1_000_000, repeat=5))
    b = min(timeit.repeat(lambda: os.getpid() != 0, number=1_000_000, repeat=5))
    print(sys.version.split()[0], 'cached pid read %.0f ns, os.getpid() %.0f ns (difference %.0f ns per open)' % (a * 1e3, b * 1e3, (b - a) * 1e3))
