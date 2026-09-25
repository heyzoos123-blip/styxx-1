# M4 side effect: does rev 2's per-section toggling of styxx's global PY_UNWIND undo another tool's DISABLE?
# Tool 1 (coverage.py sysmon's shape) returns DISABLE from its LINE and PY_START callbacks. After 1000 styxx
# sections (each sets and clears PY_UNWIND on tool 4), do tool 1's callbacks fire again for the same code?
import sys
sys.path.insert(0, __file__.rsplit('/', 1)[0])
import mech2 as mech
M = sys.monitoring; E = M.events
seen = {'line': 0, 'start': 0}
pairs = {}
def line_cb(code, line):
    seen['line'] += 1; k = (id(code), line, 'L'); pairs[k] = pairs.get(k, 0) + 1; return M.DISABLE
def start_cb(code, off):
    seen['start'] += 1; k = (id(code), off, 'S'); pairs[k] = pairs.get(k, 0) + 1; return M.DISABLE
def work():
    x = 1
    y = x + 1
    return y
M.use_tool_id(1, 'cov-model'); M.register_callback(1, E.LINE, line_cb); M.register_callback(1, E.PY_START, start_cb)
M.set_events(1, E.LINE | E.PY_START)
work(); first = dict(seen)
def target(): return 1
mech.UNWIND_SCOPE[0] = 'section'
with mech.Tracer(target) as tr:
    for _ in range(1000): tr.run('A', work)
after = dict(seen)
M.set_events(1, 0); M.free_tool_id(1)
print(sys.version.split()[0], 'tool-1 callbacks after first call', first, '| after 1000 toggling sections', after,
      '| toggles on/off', mech.STATS['toggles_on'], mech.STATS['toggles_off'],
      '| locations that fired more than once after DISABLE:', sum(1 for v in pairs.values() if v > 1), '| max fires at one location:', max(pairs.values()), '(1000 would mean DISABLE is undone at every toggle)')
