# X71c port: the id-5 injector raises a signal at the first INSTRUCTION event of a machinery
# function; the handler (ordinary code, not a monitoring callback) calls a traced target.
# Is the handler run before the function's first statement, and does the target raise events?
import signal, sys
M = sys.monitoring; E = M.events
LOG = []
def target(): LOG.append('target')
def machinery():                 # stands for _detach: its first statement pops the anchor
    LOG.append('first statement')
def handler(s, f): LOG.append('handler'); target()
signal.signal(signal.SIGUSR1, handler)
M.use_tool_id(5, 'injector'); M.use_tool_id(4, 'styxx-like')
state = {'armed': True}
def inj(code, off):
    if state['armed']:
        state["armed"] = False; (RAISE)()
M.register_callback(5, E.INSTRUCTION, inj)
M.set_local_events(5, machinery.__code__, E.INSTRUCTION)
M.register_callback(4, E.PY_START, lambda c, o: LOG.append('PY_START ' + c.co_name))
M.set_local_events(4, target.__code__, E.PY_START)
import _thread
for name, RAISE in (("raise_signal", lambda: signal.raise_signal(signal.SIGUSR1)), ("interrupt_main", lambda: _thread.interrupt_main(signal.SIGUSR1))):
    LOG.clear(); state["armed"] = True; machinery(); print(sys.version.split()[0], name, LOG)
LOG.clear(); target(); print(sys.version.split()[0], 'direct call of target:', LOG)
LOG.clear(); M.set_local_events(5, machinery.__code__, 0)
def machinery2():
    x = 1
    LOG.append('first statement')
M.set_local_events(5, machinery2.__code__, E.INSTRUCTION)
import dis
offs = [i.offset for i in dis.get_instructions(machinery2)]
for off in offs[1:3]:
    def inj2(code, o, off=off):
        if state['armed'] and o == off:
            state['armed'] = False; _thread.interrupt_main(signal.SIGUSR1)
    M.register_callback(5, E.INSTRUCTION, inj2)
    LOG.clear(); state['armed'] = True; machinery2(); print(sys.version.split()[0], 'interrupt_main at offset', off, LOG)
