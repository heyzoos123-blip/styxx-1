# rev13 (GAP-51): the 8 blind shapes of mutation_gate_blindspots.json (spec data; copy in spec_data/), each planted as
# a refusal with a fresh code, against O13 as revision 13 defines it (a coded literal's innermost enclosing statement
# replaced by `pass`). For each shape: the planted literal is found, its site compiles as `pass`, and the mutant no
# longer emits the code. The 4 computed-code shapes (no literal holds the code) are listed to show O13 sees nothing
# there; those are G_HYG's (the exam author's refcensus_v5f.py plants and catches them).
# Run: python3 p_blind8.py
import ast, json, sys
class GateSpecError(Exception): pass
SHAPES = {
 "raise via a helper that returns the exception": '''
def _refuse(t):
    return GateSpecError(t)
def plant(c):
    if c:
        raise _refuse("[V5:PLANTED] helper")
    return 0''',
 "raise GateSpecError through a module attribute": '''
import types as _t
mod = _t.SimpleNamespace(GateSpecError=GateSpecError)
def plant(c):
    if c:
        raise mod.GateSpecError("[V5:PLANTED] attribute")
    return 0''',
 "raise an alias of GateSpecError": '''
E = GateSpecError
def plant(c):
    if c:
        raise E("[V5:PLANTED] alias")
    return 0''',
 "recorded problem appended by augmented assignment": '''
problems = []
def plant(c):
    global problems
    if c:
        problems += ["[V5:PLANTED] augmented"]
    return problems[-1] if problems else 0''',
 "emission as the value of a return": '''
def _text(c):
    return "[V5:PLANTED] returned"
def plant(c):
    if c:
        raise GateSpecError(_text(c))
    return 0''',
 "emission assigned to a name": '''
def plant(c):
    if c:
        msg = "[V5:PLANTED] assigned"
        raise GateSpecError(msg)
    return 0''',
 "emission inside a conditional expression": '''
def plant(c):
    if c:
        raise GateSpecError("[V5:PLANTED] a" if c > 1 else "[V5:PLANTED] b")
    return 0''',
 "code in a keyword argument": '''
class KwError(GateSpecError):
    def __init__(self, msg=""):
        super().__init__(msg)
def plant(c):
    if c:
        raise KwError(msg="[V5:PLANTED] keyword")
    return 0''',
}
COMPUTED = {"a code prefix split across literals": '"[V5:" + "PLANTED] x"', "str.format": '"[{}:PLANTED] x".format("V5")',
            "%-formatting": '"[%s:PLANTED] x" % "V5"', "a code from an f-string's formatted value": 'f"[V5:{code}] x"'}

def coded(n):
    return isinstance(n, ast.Constant) and isinstance(n.value, str) and '[V5:' in n.value

def o13_mutants(src):
    """One mutant per coded literal: its innermost enclosing statement replaced by `pass` (docstrings excluded)."""
    tree = ast.parse(src); out = []
    parents = {}
    for p in ast.walk(tree):
        for ch in ast.iter_child_nodes(p): parents[ch] = p
    for n in ast.walk(tree):
        if not coded(n): continue
        st = n
        while not isinstance(st, ast.stmt): st = parents[st]
        t2 = ast.parse(src)
        for m in ast.walk(t2):
            for fld, val in ast.iter_fields(m):
                if isinstance(val, list):
                    for i, x in enumerate(val):
                        if isinstance(x, ast.stmt) and x.lineno == st.lineno and x.col_offset == st.col_offset and type(x) is type(st):
                            val[i] = ast.Pass(lineno=x.lineno, col_offset=x.col_offset)
        msrc = ast.unparse(ast.fix_missing_locations(t2))
        out.append((n.lineno, msrc))
    return out

def emits(src):
    g = {'GateSpecError': GateSpecError}
    exec(compile(src, '<shape>', 'exec'), g)
    try:
        v = g['plant'](1)
        return isinstance(v, str) and '[V5:PLANTED]' in v
    except GateSpecError as e:
        return '[V5:PLANTED]' in str(e)
    except Exception:
        return False

res = {}
for name, src in SHAPES.items():
    ms = o13_mutants(src)
    res[name] = {'original_emits': emits(src), 'coded_literals': len(ms),
                 'every_mutant_compiles': all(compile(m, '<m>', 'exec') for _, m in ms),
                 'mutants_still_emitting': sum(emits(m) for _, m in ms)}
comp = {name: {'coded_literals_O13_sees': len([n for n in ast.walk(ast.parse(expr)) if coded(n)])} for name, expr in COMPUTED.items()}
print(json.dumps({'python': sys.version.split()[0], 'blind_shapes_v5': res, 'computed_code_shapes': comp}, indent=1))
