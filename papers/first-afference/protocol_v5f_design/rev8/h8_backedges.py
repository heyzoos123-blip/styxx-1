# Revision 8 (rev8/steps8.py, the tee registration); Revision 7, H (CPython #130279): no backward jump in any of M7's five step functions as revision 7 writes them
# (rev7/steps7.py: _register now counts inside its call).
import sys, os, dis
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import steps8 as steps7
def backedges(code):
    return [(i.offset, i.opname) for i in dis.get_instructions(code) if 'BACKWARD' in i.opname]
v = sys.version.split()[0]
for name, code in steps7._v5_faultpoints().items():
    print(v, 'steps8', '%-12s' % name, 'backward jumps:', backedges(code) or 'none')
# mech7.py is not checked: its step functions carry mutant-only branches (list comprehensions in no_gate, gate_split,
# on_capture_split), whose loops are not the spec's code. _commit, _detach and _run are unchanged from revision 6.
