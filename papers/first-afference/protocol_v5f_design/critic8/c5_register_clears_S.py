# critic8/c5: the self-audit (Appendix A, id 107) says "_register never writes S" is witnessed by "G_HYG (set_events only
# in the other steps); G_ATOM state criterion (d)". G_HYG has no such clause: statement 1 may bind any `_MON[0][i]`, and
# `set_events` is allowed in "the step functions", of which _register is one. K13 below is _register with a gated
# set_events(t, 0) chained in front, its None result swallowed by `_filter(None, ...)` (allowed by G_HYG), so r is
# unchanged. Every name it uses is in G_HYG's list. Does G_ATOM's 64-case matrix see it? (All 9 _register cases start
# with the global event clear, so a clear changes nothing observable.)
import sys, os, json, subprocess
REV7 = '/home/user/styxx-1/papers/first-afference/protocol_v5f_design/rev7'
sys.path.insert(0, REV7)
import atom7
atom7.PATCHES['K13'] = ('''    get_tool, register_callback = _MON[0][0], _MON[0][4]
    return _list(_chain(''', '''    get_tool, register_callback, set_events = _MON[0][0], _MON[0][4], _MON[0][2]
    return _list(_chain(
        _filter(None, _map(set_events, _compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)), _ZERO1)),''')
if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'run':
        print(json.dumps(atom7.run_variant(sys.argv[2]), default=repr)); sys.exit(0)
    v = sys.version.split()[0]
    for variant in ('ref', 'K13'):
        p = subprocess.run([sys.executable, __file__, 'run', variant], capture_output=True, text=True, timeout=300)
        if not p.stdout.strip(): print(v, variant, 'ERROR', p.stderr[-600:]); continue
        r = json.loads(p.stdout.strip().splitlines()[-1])
        print(v, '%-4s %d of %d cases fail%s' % (variant, r['failed'], r['cases'],
              ' -> NOT DETECTED' if r['failed'] == 0 and variant != 'ref' else ''), r['first_failures'][:1], flush=True)
