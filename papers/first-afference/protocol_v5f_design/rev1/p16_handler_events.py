# Does code run by a signal handler raise sys.monitoring events (a) when the signal lands in ordinary
# code, (b) when it is tripped from inside another tool's INSTRUCTION callback (the X71c port idea)?
import signal, sys, _thread, time
M = sys.monitoring; E = M.events
LOG = []
def target(): LOG.append('target')
def handler(s, f): target()
signal.signal(signal.SIGUSR1, handler)
M.use_tool_id(4, 'styxx-like')
M.register_callback(4, E.PY_START, lambda c, o: LOG.append('PY_START'))
M.set_local_events(4, target.__code__, E.PY_START)
_thread.interrupt_main(signal.SIGUSR1)
x = 0
for i in range(1000): x += i
print(sys.version.split()[0], '(a) handler tripped from ordinary code:', LOG)
LOG.clear()
M.use_tool_id(3, 'fault')                      # the exam's id-3 fault tool, PY_START on a machinery fn
def machinery(): LOG.append('first statement')
armed = [True]
def pystart(code, off):
    if armed[0]: armed[0] = False; _thread.interrupt_main(signal.SIGUSR1)
M.register_callback(3, E.PY_START, pystart)
M.set_local_events(3, machinery.__code__, E.PY_START)
machinery()
print(sys.version.split()[0], '(b) tripped from a PY_START callback of tool 3:', LOG)
LOG.clear(); armed[0] = True
M.set_local_events(3, machinery.__code__, 0)
M.use_tool_id(5, 'inj')
M.register_callback(5, E.INSTRUCTION, lambda c, o: (armed[0] and (armed.__setitem__(0, False), _thread.interrupt_main(signal.SIGUSR1))) and None)
M.set_local_events(5, machinery.__code__, E.INSTRUCTION)
machinery()
print(sys.version.split()[0], '(c) tripped from an INSTRUCTION callback of tool 5:', LOG)
