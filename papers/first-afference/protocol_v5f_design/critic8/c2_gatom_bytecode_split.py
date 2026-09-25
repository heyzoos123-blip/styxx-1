# critic8/c2: can G_ATOM's criteria (a)-(d) (spec lines ~2051-2066) be passed by a step whose work is split across
# bytecode rather than across C calls? Criterion (c) sees only c_call events from sys.setprofile (PyCFunction and
# method descriptors). Reads by BINARY_SUBSCR / CONTAINS_OP and calls of method-wrappers (e.g. list.__iadd__) are
# invisible to it. Two frozen-text patches of rev7/steps7.py, run through rev7/atom7.py's own harness unchanged:
#   K11  _register counting AFTER its consuming call (the F26 fault window), via _LOST.__iadd__ and an inlined
#        list comprehension (no PyCFunction call outside the interval);
#   K12  _unwind_on whose own-anchor gate is read by bytecode (`in` and subscript) in the binding statement, before
#        the consuming call: a test-then-act split across an eval-breaker boundary.
# If G_ATOM reports 0 failing cases for a variant, the gate cannot tell it from the reference. (G_HYG, which is static,
# would reject both shapes; the point is what G_ATOM itself, and the self-audit's citation of it, can witness.)
import sys, os, json, subprocess
REV7 = '/home/user/styxx-1/papers/first-afference/protocol_v5f_design/rev7'
sys.path.insert(0, REV7)
import atom7
atom7.PATCHES['K11'] = ('''    return _list(_chain(
        _map(_LOST_APPEND, _filter(None, _map(_is_not,
            _map(register_callback,
                 _compress(_repeat(t), _map(_is, _map(get_tool, _repeat(t, 5)), _repeat(_TOOL_NAME))),
                 _EVENTS5, _CALLBACKS5),
            _CALLBACKS5))),
        _map(get_tool, (t,))))''', '''    r = _list(_chain(
        _map(register_callback,
             _compress(_repeat(t), _map(_is, _map(get_tool, _repeat(t, 5)), _repeat(_TOOL_NAME))),
             _EVENTS5, _CALLBACKS5),
        _map(get_tool, (t,))))
    _LOST.__iadd__([True for x in _filter(None, _map(_is_not, r[:-1], _CALLBACKS5))])
    return [None for x in _filter(None, _map(_is_not, r[:-1], _CALLBACKS5))] + r[-1:]''')
atom7.PATCHES['K12'] = ('''def _unwind_on(o):
    t, get_tool, get_events, set_events = _TOOL[0], _MON[0][0], _MON[0][1], _MON[0][2]''', '''def _unwind_on(o):
    t, get_tool, get_events, set_events, own = _TOOL[0], _MON[0][0], _MON[0][1], _MON[0][2], (o.frame in _ANCHORS and _ANCHORS[o.frame] is o)''')
# K12 also replaces both in-call own-anchor gates by the precomputed bool
_old_load = atom7.load
def load(variant):
    if variant != 'K12': return _old_load(variant)
    src = open(os.path.join(REV7, 'steps7.py')).read()
    old, new = atom7.PATCHES['K12']; assert src.count(old) == 1; src = src.replace(old, new)
    g = '_map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))'; assert src.count(g) == 2; src = src.replace(g, '(own,)')
    import types
    mod = types.ModuleType('steps7_K12'); mod.__file__ = os.path.join(REV7, 'steps7.py')
    exec(compile(src, mod.__file__, 'exec'), vars(mod)); return mod
atom7.load = load

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'run':
        print(json.dumps(atom7.run_variant(sys.argv[2]), default=repr)); sys.exit(0)
    v = sys.version.split()[0]
    for variant in ('ref', 'K10', 'K11', 'K12'):
        p = subprocess.run([sys.executable, __file__, 'run', variant], capture_output=True, text=True, timeout=300)
        if not p.stdout.strip(): print(v, variant, 'ERROR', p.stderr[-600:]); continue
        r = json.loads(p.stdout.strip().splitlines()[-1])
        print(v, '%-4s %d of %d cases fail%s' % (variant, r['failed'], r['cases'],
              ' -> NOT DETECTED: G_ATOM passes this mutant' if r['failed'] == 0 and variant != 'ref' else ''),
              r['first_failures'][:1], flush=True)
