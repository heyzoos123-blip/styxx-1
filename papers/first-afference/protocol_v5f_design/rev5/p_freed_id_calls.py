# Which sys.monitoring calls raise on a freed id? (revision 5: the close's event read needs no name test; every write
# that can raise is inside a one-call step gated on the name, so none is attempted on an id styxx does not hold)
import sys; M = sys.monitoring
M.use_tool_id(4, 'x'); M.set_events(4, M.events.PY_UNWIND); M.free_tool_id(4)
out = {}
for name, fn in (('get_events', lambda: M.get_events(4)), ('get_local_events', lambda: M.get_local_events(4, (lambda: 0).__code__)),
                 ('set_events', lambda: M.set_events(4, 0)), ('set_local_events', lambda: M.set_local_events(4, (lambda: 0).__code__, 0)),
                 ('register_callback', lambda: M.register_callback(4, M.events.PY_START, None)), ('get_tool', lambda: M.get_tool(4))):
    try: out[name] = ('ok', fn())
    except Exception as e: out[name] = (type(e).__name__, str(e))
print(sys.version.split()[0], out)
