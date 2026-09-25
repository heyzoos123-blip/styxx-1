# Revision 8: the new witness rows, through rev8/w8_witnesses.py's own child (one fresh subprocess per trial, mech8.py).
#   X158c (N4)  X158 with the outside party registering None over styxx's PY_START callback. Mutant count_excl_none:
#               a registration that does not count None previous callbacks.
#   N1 probe    MUT take_count (not the spec): each _take appends to _LOST inside its own consuming call. Run on X157b
#               (F25's residual), and combined with the mutants whose witnesses it could mask: X137h7 with
#               rebind_count_none, X154d (a) with retake_nocount, X154d (b) with rebind_count_none.
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w8_witnesses as w
if __name__ == '__main__':
    for mut in (None, 'count_excl_none'):
        for order in ('P-first', 'Q-first'): w.run('X158c', mut, order)
    for mut in (None, 'take_count'): w.run('X157b', mut)
    for mut in ('rebind_count_none', 'take_count', 'take_count+rebind_count_none'): w.run('X137h7', mut)
    for mut in ('retake_nocount', 'take_count', 'take_count+retake_nocount'): w.run('X154d', mut, 'free')
    for mut in ('take_count+rebind_count_none',): w.run('X154d', mut, 'take')
    for mut in (None, 'rebind_count_none'): w.run('X137h7', mut, 'all')   # revision 8 (N7): P's, Q's and S's outcomes too
