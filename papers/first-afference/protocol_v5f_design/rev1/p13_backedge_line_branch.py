# Same as p12 for LINE and BRANCH local events (LINE is the event of the draft's named alternative,
# "first-LINE confirmation").
import signal, sys, random
exec(open(__file__.replace('p13_backedge_line_branch.py', 'p12_backedge_under_styxx_events.py')).read().split("v = sys.version")[0])
v = sys.version.split()[0]
M.use_tool_id(5, 'probe')
for ev in ('LINE', 'BRANCH'):
    M.register_callback(5, getattr(E, ev), lambda *a: None)
    for fn in (while_try, while_with): M.set_local_events(5, fn.__code__, getattr(E, ev))
    print(v, ev, "events:", "while_try skipped", run(while_try, 100), "| while_with skipped", run(while_with, 100))
    for fn in (while_try, while_with): M.set_local_events(5, fn.__code__, 0)
