# M3: a party frees styxx's tool id during a trace, then the trace exits normally. Does a process-wide callback
# into styxx outlive the completed exit? rev 1: exit never touches an id that lost its name. rev 2: exit re-takes
# the id when it is unowned (get_tool is None), clears its events and notes MONITOR_LOST.
# Variant: another tool takes the freed id before exit (styxx must not touch it; disclosed).
import sys
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech2 as mech
M = sys.monitoring; E = M.events
calls = [0]
orig_unwind = mech._on_unwind
def counting_unwind(code, offset, exc):
    calls[0] += 1; return orig_unwind(code, offset, exc)
mech._on_unwind = counting_unwind                   # install_tool registers mech._on_unwind by name
def f(): return 1
def g(): return 2
def _raiser(): raise KeyError
def unrelated():                                    # the KeyError unwinds one frame: one PY_UNWIND event
    try: _raiser()
    except KeyError: pass

def scenario(scope, reclaim, taken):
    mech.UNWIND_SCOPE[0] = scope; mech.RECLAIM[0] = reclaim
    with mech.Tracer(f, g) as tr:
        def body():
            f(); M.free_tool_id(4)
            if taken: M.use_tool_id(4, 'other-tool')
            g()
        tr.run('A', body)
    r = tr.result()
    calls[0] = 0
    for _ in range(1000): unrelated()
    st = mech.state()
    out = '%-9s reclaim=%-5s taken=%-5s | record %s MONITOR_LOST=%s | after exit: tool=%r global_events=%d, unwind callbacks for 1000 unrelated raises: %d' % (
        scope, reclaim, taken, r['calls'], r['MONITOR_LOST'], st['tool_name'], st['global_events'], calls[0])
    if M.get_tool(4) is not None:                   # clean up for the next scenario
        M.set_events(4, 0); M.free_tool_id(4)
    return out

ver = sys.version.split()[0]
for scope, reclaim, taken in (('mint', False, False), ('section', False, False), ('section', True, False),
                              ('mint', True, False), ('section', True, True)):
    print(ver, scenario(scope, reclaim, taken))
