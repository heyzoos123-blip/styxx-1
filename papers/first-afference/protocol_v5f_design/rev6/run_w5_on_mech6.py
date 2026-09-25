# Regression: revision 5's witnesses (rev5/w5_witnesses.py) run against rev6/mech6.py in place of mech5.py.
import sys, os, runpy
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mech6
sys.modules['mech5'] = mech6
W5 = '/home/user/styxx-1/papers/first-afference/protocol_v5f_design/rev5/w5_witnesses.py'
sys.argv = [W5]
runpy.run_path(W5, run_name='__main__')
