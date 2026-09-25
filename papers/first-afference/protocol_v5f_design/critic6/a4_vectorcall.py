# Which one-call callables go through tp_call (=> _PyObject_MakeTpCall => C recursion check => RecursionError can be
# raised INSIDE the consuming call, i.e. a fault inside a "one-call step")?
import sys, operator, itertools, collections
HV = 1 << 11
cands = {'operator.attrgetter instance': operator.attrgetter('a'), 'operator.is_': operator.is_,
         'operator.setitem': operator.setitem, 'dict.values': dict.values, '{}.get': {}.get, '{}.pop': {}.pop,
         'itertools.repeat (type)': itertools.repeat, 'sys.monitoring.set_events': sys.monitoring.set_events,
         'sys.monitoring.register_callback': sys.monitoring.register_callback}
for k, c in cands.items():
    t = type(c)
    print(sys.version.split()[0], k, 'vectorcall' if (t.__flags__ & HV) else 'tp_call', t.__name__)
