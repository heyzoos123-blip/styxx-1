# Revision 7: the seventh critic's c1 (critic7/c1_cbrepair_two_traces.py) run unchanged against mech7.py (spec) and
# against mech7 with MUT 'cbrep_nocount' (revision 6's rule), through a sys.modules alias.
import sys, os, runpy
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import mech7
sys.modules['mech6'] = mech7
mut = sys.argv[1] if len(sys.argv) > 1 else ''
if mut:
    _reset = mech7.reset
    def reset():
        _reset(); mech7.MUT.add(mut)
    mech7.reset = reset
print('mech7', mut or 'spec', flush=True)
runpy.run_path(os.path.join(HERE, '..', 'critic7', 'c1_cbrepair_two_traces.py'), run_name='__main__')
