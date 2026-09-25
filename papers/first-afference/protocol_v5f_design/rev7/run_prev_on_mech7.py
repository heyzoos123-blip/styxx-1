# Revision 7: re-run revision 5's and revision 6's witness files against mech7.py in place of mech5.py / mech6.py
# (sys.modules aliases), to show revision 7's changes alter no earlier verdict.
import sys, os, runpy
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
which = sys.argv[1]
import mech7
sys.modules['mech5'] = mech7; sys.modules['mech6'] = mech7
path = {'w5': '../rev5/w5_witnesses.py', 'w6': '../rev6/w6_witnesses.py', 'b1': '../rev6/r6_b1_register.py',
        'green': '../rev6/w6_greenlet.py'}[which]
sys.argv = [os.path.join(HERE, path)] + sys.argv[2:]
runpy.run_path(os.path.join(HERE, path), run_name='__main__')
