# G_COVER: can a line-coverage instrument see lines executed inside a sys.monitoring callback?
# styxx's _on_entry/_on_exit/_on_unwind/_outcome/_publish run only there.
import sys
M = sys.monitoring; E = M.events
seen_settrace, seen_mon = set(), set()
def cb_body(code, off):                 # stands for _on_entry -> _outcome -> _publish
    x = 1
    y = x + 1
    return None
def target(): return 1
def tracer(frame, event, arg):
    if frame.f_code is cb_body.__code__ and event == 'line': seen_settrace.add(frame.f_lineno)
    return tracer
def line_cb(code, line):
    if code is cb_body.__code__: seen_mon.add(line)
M.use_tool_id(4, 'styxx-model'); M.register_callback(4, E.PY_START, cb_body)
M.set_local_events(4, target.__code__, E.PY_START)
M.use_tool_id(1, 'coverage-model'); M.register_callback(1, E.LINE, line_cb)
M.set_local_events(1, cb_body.__code__, E.LINE)
sys.settrace(tracer)
target()
sys.settrace(None)
print(sys.version.split()[0], 'lines of the callback seen: settrace', sorted(seen_settrace), '| sys.monitoring LINE', sorted(seen_mon))
cb_body(None, 0)                        # the same function called outside a callback
print(sys.version.split()[0], 'called directly: sys.monitoring LINE', sorted(seen_mon))
