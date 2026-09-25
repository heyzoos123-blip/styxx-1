# Revision 8 (the eighth critic's M2 and M3): a prototype of G_HYG's step-function clauses as revision 8 states them,
# run on rev8/steps8.py and on the frozen text patches K4-K14 (rev8/atom8.py's PATCHES). Static only (ast).
#   S1 statement count: _register has exactly three statements, every other step exactly two.
#   S2 the first statement is one assignment of locals from _TOOL[0] (only in _unwind_on and _unwind_off) and _MON[0][i]
#      with literal i, and each step binds exactly its frozen index set under the frozen names (revision 8, M3):
#      _unwind_on {t, 0 get_tool, 1 get_events, 2 set_events}; _unwind_off {t, 0, 2}; _take {0, 5 use_tool_id};
#      _register {0, 4 register_callback}; _set_local {0, 3 set_local_events}.
#   S3 _register's second statement is `a, b = _tee(<pipeline>)`; the last statement is `_CONSUME(...)` (an expression
#      statement) or, in _register, `return _list(...)`.
#   S4 the pipeline statements name only the allowed names; every call is of an allowed callable or a bound _MON local;
#      no lambda, comprehension, generator expression, subscript, comparison, boolean operator or conditional; _tee only
#      in _register's second statement; _is_not and _LOST_APPEND only in _register; _CALLBACKS5 only as an argument of
#      _map in _register; the literal None only as _filter's first argument or _repeat's argument.
import sys, os, ast
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import atom8
MON = {0: 'get_tool', 1: 'get_events', 2: 'set_events', 3: 'set_local_events', 4: 'register_callback', 5: 'use_tool_id'}
FROZEN = {'_unwind_on': ({'t'}, {0, 1, 2}), '_unwind_off': ({'t'}, {0, 2}), '_take': (set(), {0, 5}),
          '_register': (set(), {0, 4}), '_set_local': (set(), {0, 3})}
PARAMS = {'_unwind_on': {'o'}, '_unwind_off': {'key'}, '_take': {'t'}, '_register': {'t'}, '_set_local': {'t', 'code', 'events'}}
VOCAB = {'_map', '_chain', '_compress', '_filter', '_is', '_not', '_and', '_setitem', '_ARMED', '_FLAGS', '_VALUES',
         '_CONSUME', '_LOST_KEY', '_TRUE', '_PYU1', '_ZERO1', '_NONE1', '_NAME1', '_repeat', '_list', '_EVENTS5',
         '_CALLBACKS5', '_TOOL_NAME', '_is_not', '_LOST_APPEND', '_tee', '_ANCHORS'}
CTORS = {'_map', '_chain', '_compress', '_filter', '_repeat', '_list', '_CONSUME', '_tee'}

def source(variant):
    src = open(os.path.join(HERE, 'steps8.py')).read()
    if variant == 'ref': return src
    old, new = atom8.PATCHES[variant]; assert src.count(old) == 1, variant; src = src.replace(old, new)
    if variant == 'K12': src = src.replace(*atom8.K12_GATE)
    if variant == 'K13': src = src.replace(*atom8.K13_CHAIN)
    if variant == 'K6': src = src.replace(*atom8.K6_FIX)
    return src

def lint(src):
    tree = ast.parse(src); bad = []
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name, (tset, idx) in FROZEN.items():
        fn = funcs.get(name)
        if fn is None: bad.append((name, 'S1', 'missing')); continue
        body = fn.body
        want = 3 if name == '_register' else 2
        if len(body) != want: bad.append((name, 'S1', '%d statements' % len(body))); continue
        s1 = body[0]; bound = {}
        ok1 = isinstance(s1, ast.Assign) and len(s1.targets) == 1
        if ok1:
            tg, vl = s1.targets[0], s1.value
            tgs = tg.elts if isinstance(tg, ast.Tuple) else [tg]; vls = vl.elts if isinstance(vl, ast.Tuple) else [vl]
            ok1 = len(tgs) == len(vls) and all(isinstance(x, ast.Name) for x in tgs)
            if ok1:
                for tn, v in zip(tgs, vls):
                    if ast.unparse(v) == '_TOOL[0]': bound[tn.id] = 't'
                    elif (isinstance(v, ast.Subscript) and ast.unparse(v.value) == '_MON[0]' and isinstance(v.slice, ast.Constant)
                          and isinstance(v.slice.value, int)): bound[tn.id] = v.slice.value
                    else: ok1 = False; bad.append((name, 'S2', 'statement 1 binds %s' % ast.unparse(v)))
        if not ok1: bad.append((name, 'S2', 'statement 1 is not one assignment of _TOOL[0] and _MON[0][i]')); continue
        got_t = {v for v in bound.values() if v == 't'}; got_i = {v for v in bound.values() if v != 't'}
        if got_t != tset or got_i != idx or any(k != (MON[v] if v != 't' else 't') for k, v in bound.items()):
            bad.append((name, 'S2', 'binds %s; frozen %s' % (sorted(bound.items()), sorted(tset | {MON[i] for i in idx}))))
        locs = set(bound) | PARAMS[name]
        pipes = body[1:]
        if name == '_register':
            s2 = body[1]
            if not (isinstance(s2, ast.Assign) and isinstance(s2.targets[0], ast.Tuple) and len(s2.targets[0].elts) == 2
                    and all(isinstance(x, ast.Name) for x in s2.targets[0].elts) and isinstance(s2.value, ast.Call)
                    and ast.unparse(s2.value.func) == '_tee' and len(s2.value.args) == 1):
                bad.append((name, 'S3', 'statement 2 is not `a, b = _tee(<pipeline>)`'))
            else: locs |= {x.id for x in s2.targets[0].elts}
        last = body[-1]
        if name == '_register':
            if not (isinstance(last, ast.Return) and isinstance(last.value, ast.Call) and ast.unparse(last.value.func) == '_list'):
                bad.append((name, 'S3', 'last statement is not `return _list(...)`'))
        elif not (isinstance(last, ast.Expr) and isinstance(last.value, ast.Call) and ast.unparse(last.value.func) == '_CONSUME'):
            bad.append((name, 'S3', 'last statement is not `_CONSUME(...)`'))
        for k, st in enumerate(pipes):
            root = st.value
            for node in ast.walk(root):
                if isinstance(node, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Subscript,
                                     ast.Compare, ast.BoolOp, ast.IfExp, ast.BinOp, ast.UnaryOp, ast.NamedExpr, ast.Starred)):
                    bad.append((name, 'S4', '%s in a pipeline statement' % type(node).__name__)); continue
                if isinstance(node, ast.Attribute):
                    a = ast.unparse(node)
                    if a not in ('o.frame', '_ANCHORS.get', '_ANCHORS.pop', '_chain.from_iterable'):
                        bad.append((name, 'S4', 'attribute %s' % a))
                if isinstance(node, ast.Name) and not (node.id in VOCAB or node.id in locs):
                    bad.append((name, 'S4', 'name %s' % node.id))
                if isinstance(node, ast.Name) and node.id in ('_is_not', '_LOST_APPEND') and name != '_register':
                    bad.append((name, 'S4', '%s outside _register' % node.id))
                if isinstance(node, ast.Name) and node.id == '_tee' and not (name == '_register' and k == 0):
                    bad.append((name, 'S4', '_tee outside _register\'s second statement'))
                if isinstance(node, ast.Call):
                    fnm = ast.unparse(node.func)
                    if not (fnm in CTORS or fnm == '_chain.from_iterable' or fnm in bound):
                        bad.append((name, 'S4', 'call of %s' % fnm))
                    for j, a in enumerate(node.args):
                        if isinstance(a, ast.Constant) and a.value is None and not ((fnm == '_filter' and j == 0) or fnm == '_repeat'):
                            bad.append((name, 'S4', 'None as argument %d of %s' % (j, fnm)))
                        if isinstance(a, ast.Name) and a.id == '_CALLBACKS5' and not (fnm == '_map' and name == '_register'):
                            bad.append((name, 'S4', '_CALLBACKS5 as an argument of %s' % fnm))
    return bad

if __name__ == '__main__':
    v = sys.version.split()[0]
    for variant in ['ref'] + ['K%d' % i for i in range(4, 15)] + ['K12b']:
        b = lint(source(variant))
        if variant == 'ref': print(v, 'G_HYG steps (revision 8 prototype) on steps8.py:', 'PASS' if not b else 'FAIL %s' % b)
        else: print(v, 'control %-4s %s' % (variant, ('REJECTED %s' % b[:3]) if b else 'NOT REJECTED'))
