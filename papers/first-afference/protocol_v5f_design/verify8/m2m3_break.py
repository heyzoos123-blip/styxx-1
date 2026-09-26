# verify8: attempts to get a step mutant past BOTH G_HYG (rev8/hyg8.py) and G_ATOM (rev8/atom8.py).
#   V1 (M1/M2): _register with the tee placed on the COMPARISON results, not on the exchanges: the previous callbacks
#       are dropped by map right after _is_not, before the count (revision 7's hole, dressed in revision 8's shape).
#   V2 (M2): _take reading the owner at build time through a direct call of the bound get_tool, no operator:
#       _compress((t,), _map(_is, (get_tool(t),), _NONE1)).
#   V3 (M2): _unwind_off reading _ANCHORS at build time through a direct call of _ANCHORS.get (the text's name list
#       allows _ANCHORS.get as a name; the call is outside the consumer).
#   V4 (M3): _register writing S through register_callback? impossible; instead _register reads get_events? not bound.
#       V4 = _register binding an allowed index under a WRONG name (set_events = _MON[0][4]) - checks name freezing.
import sys, os, json, subprocess
R8 = '/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/v5f/rev8'
sys.path.insert(0, R8)
import atom8, hyg8
REG8 = atom8.REG8
EXTRA = {
 'V1': (REG8, '''    a, b = _tee(_map(_is_not, _map(register_callback,
                     _compress(_repeat(t), _map(_is, _map(get_tool, _repeat(t, 5)), _repeat(_TOOL_NAME))),
                     _EVENTS5, _CALLBACKS5), _CALLBACKS5))
    return _list(_chain(
        _map(_LOST_APPEND, _map(_is_not, _filter(None, a), _repeat(None))),
        _map(get_tool, (t,))))'''),
 'V2': ('''    _CONSUME(_map(use_tool_id, _compress((t,), _map(_is, _map(get_tool, (t,)), _NONE1)), _NAME1))''',
        '''    _CONSUME(_map(use_tool_id, _compress((t,), _map(_is, (get_tool(t),), _NONE1)), _NAME1))'''),
 'V3': ('''                       _map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))),
             _PYU1)))''', '''                       _map(_is, (_ANCHORS.get(o.frame),), (o,))),
             _PYU1)))'''),
 'V4': ('''    get_tool, register_callback = _MON[0][0], _MON[0][4]
    a, b = _tee(''', '''    get_tool, register_callback = _MON[0][0], _MON[0][4]
    a, b = _tee(''')  # placeholder: identical (sanity: must PASS both)
}
atom8.PATCHES.update(EXTRA)
if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'run':
        r = atom8.run_variant(sys.argv[2]); print(json.dumps(dict(failed=r['failed'], cases=r['cases'], first=r['first_failures'][:2]), default=repr)); sys.exit(0)
    v = sys.version.split()[0]
    for k in EXTRA:
        src = open(os.path.join(R8, 'steps8.py')).read()
        old, new = EXTRA[k]; assert src.count(old) == 1, k
        b = hyg8.lint(src.replace(old, new))
        p = subprocess.run([sys.executable, __file__, 'run', k], capture_output=True, text=True, timeout=300)
        out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else 'ERROR ' + p.stderr[-500:]
        print(v, k, 'G_HYG:', ('REJECTED %s' % b[:2]) if b else 'PASS', '| G_ATOM:', out[:420], flush=True)
