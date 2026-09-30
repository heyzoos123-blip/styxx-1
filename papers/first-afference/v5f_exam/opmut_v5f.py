"""opmut_v5f.py: the SM2 operator generator (G_SEM), written by the exam author from the v5f text ("SM2").

Region (defined by name, not by a marker): the code objects of the implementation's frozen
`_v5_faultpoints()` functions (M10); the scoring functions `Experiment._check_coverage`,
`Experiment.check_metrics`, `Experiment.score`, `_check_trace_shape` and the module-level `_finite` (M11,
GAP-08); and the module-level statements that bind the M1 names (the block of M1, with `_GUARD`'s set after
`class _Txn`).

Operators, applied mechanically at every applicable site of the Region (D1's O1-O14 and D3's families):
  deletion      O1 delete a statement; O13 refusal deletion by coded literal (a str constant or f-string part
                containing "[V5:" -> its innermost enclosing statement becomes `pass`)
  conditions    O2 negate a test; O3 drop one operand of and/or; IF a test -> True / False; QUANT any <-> all
  comparisons   O4 is <-> ==, is not <-> !=; CMP == <-> !=, < <-> <=, > <-> >=; O6 in <-> not in
  types         O5 exact type <-> isinstance/issubclass, both directions
  constants     O7 every int constant +-1; O7b every float constant x0.5 and x2
  order         O8/SWAP swap adjacent simple statements; O14 swap two sequential `if ...: raise GateSpecError`
  claims        O9 `d.setdefault(k, v) is v` -> unconditional store
  scope         O10/ITER `for x in seq` -> seq[:1] / seq[-1:]; SLICE [a:] -> [a:a+1]; O11 delete a `break`
  immutability  O12 tuple rebuild -> in-place mutation: NOT GENERATED (SPEC_GAPS.md GAP-58)
A mutant is the implementation's file with one Region node (a function, or one module-level statement)
replaced by its mutated form (ast.unparse, re-indented); nothing else in the file changes.

TCE: a mutant whose compiled module is byte-identical to the original's (bytecode, names, consts, flags,
argument counts, variable names, recursively; line tables and positions are not code) is equivalent by
construction and is not run.

Instruments, in order, stopping at the first that detects the mutant:
  (a) the frozen exam in mutation mode (`--mutation ALL`, one fresh process per mutant, each run twice);
  (b) crash_sweep_v5f.py at the frozen stride 3;
  (c) fuzz_v5f.py with its frozen seeds and N;
  (d) diffprobe_v5f.py over corpus_v5f/ against the unmutated implementation, with the recorded mask.
Classes: KILLED ((a), (b) or (c) detects it, or the mutant does not import); EXAM_HOLE (only (d)); UNDISTINGUISHED.

Usage:
  python opmut_v5f.py --list [--impl PATH]                      (counts per family and operator, TCE included)
  python opmut_v5f.py --write DIR [--impl PATH]                 (every non-TCE mutant as a file, and index.json)
  python opmut_v5f.py --run DIR --mask MASK.json [--only id,id] [--instruments abcd] --out RESULT.jsonl (resumable)
"""
import ast, copy, importlib.util, json, os, subprocess, sys, textwrap, time, types

HERE = os.path.dirname(os.path.abspath(__file__))
ARGV = list(sys.argv)


def _opt(n, d=None):
    return ARGV[ARGV.index(n) + 1] if n in ARGV else d


IMPL = os.path.abspath(_opt("--impl", os.path.join(HERE, "ref_v5f.py")))
DEPS = _opt("--deps", os.environ.get("V5F_DEPS_PATH"))

SCORING = ("Experiment._check_coverage", "Experiment.check_metrics", "Experiment.score", "_check_trace_shape",
           "_finite")
M1_NAMES = {"PY_START", "PY_RESUME", "PY_RETURN", "PY_YIELD", "PY_UNWIND", "_TRACER_ID", "_CACHE_WRAPPER",
            "_BY_FN", "_MINTED", "_ANCHORS", "_CUT", "_GUARD", "_TOOL", "_TOOL_NAME", "_HANDLE_DICT", "_LOOP_DICT",
            "_LOST", "_BUSY_SECONDS", "_LOCAL", "_map", "_chain", "_compress", "_filter", "_is", "_not", "_and",
            "_setitem", "_ARMED", "_FLAGS", "_VALUES", "_CONSUME", "_LOST_KEY", "_TRUE", "_PYU1", "_ZERO1",
            "_NONE1", "_NAME1", "_repeat", "_list", "_is_not", "_LOST_APPEND", "_tee", "_EVENTS5", "_CALLBACKS5",
            "_MON", "_get_running_loop", "_VERIFIED", "_monotonic", "_sleep"}
FAMILY = {"O1": "deletion", "O13": "deletion", "O2": "conditions", "O3": "conditions", "IF": "conditions",
          "QUANT": "conditions", "O4": "comparisons", "CMP": "comparisons", "O6": "comparisons", "O5": "types",
          "O7": "constants", "O7b": "constants", "O8": "order", "O14": "order", "O9": "claims", "O10": "scope",
          "SLICE": "scope", "O11": "scope", "O12": "immutability"}
FAMILIES = ("deletion", "conditions", "comparisons", "types", "constants", "order", "claims", "scope", "immutability")


# ---------------------------------------------------------------------------------------------------
# the Region
# ---------------------------------------------------------------------------------------------------
def load(path):
    spec = importlib.util.spec_from_file_location("opmut_region_probe", path)
    m = importlib.util.module_from_spec(spec)
    sys.modules["opmut_region_probe"] = m
    spec.loader.exec_module(m)
    return m


def region(src, mod):
    """-> [(label, node, parent_list_owner)]: the Region's AST nodes, from the source, by name."""
    tree = ast.parse(src)
    want = {}
    for k, code in mod._v5_faultpoints().items():
        want[(code.co_qualname if hasattr(code, "co_qualname") else k, code.co_firstlineno)] = k
    for q in SCORING:
        obj = mod
        for part in q.split("."):
            obj = getattr(obj, part)
        c = obj.__code__
        want[(c.co_qualname if hasattr(c, "co_qualname") else q, c.co_firstlineno)] = q
    out = []

    def visit(body, prefix):
        for n in body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                q = prefix + n.name
                first = min([n.lineno] + [d.lineno for d in n.decorator_list])
                for key in ((q, n.lineno), (q, first)):
                    if key in want:
                        out.append((want.pop(key), n))
                        break
            elif isinstance(n, ast.ClassDef):
                visit(n.body, prefix + n.name + ".")
            elif not prefix and isinstance(n, (ast.Assign, ast.AnnAssign, ast.AugAssign, ast.If)):
                names = set()
                for x in ast.walk(n):
                    if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store):
                        names.add(x.id)
                if names & M1_NAMES:
                    out.append((f"<module>:{n.lineno}:" + ",".join(sorted(names & M1_NAMES)), n))
    visit(tree.body, "")
    missing = sorted(set(want.values()))
    return tree, out, missing


# ---------------------------------------------------------------------------------------------------
# the operators: each yields (operator, description, transform) where transform(copy_of_node) mutates it
# ---------------------------------------------------------------------------------------------------
def _stmt_lists(node):
    """Every statement list inside node (its own body included), as (owner, field)."""
    for x in ast.walk(node):
        for f in ("body", "orelse", "finalbody"):
            v = getattr(x, f, None)
            if isinstance(v, list) and v and isinstance(v[0], ast.stmt):
                yield x, f
        if isinstance(x, ast.Try) or (hasattr(ast, "TryStar") and isinstance(x, ast.TryStar)):
            for h in x.handlers:
                yield h, "body"


def _has_coded_literal(n):
    for x in ast.walk(n):
        if isinstance(x, ast.Constant) and type(x.value) is str and "[V5:" in x.value:
            return True
    return False


def _is_raise_gse(s):
    return (isinstance(s, ast.If) and len(s.body) == 1 and isinstance(s.body[0], ast.Raise) and not s.orelse
            and isinstance(s.body[0].exc, ast.Call) and isinstance(s.body[0].exc.func, ast.Name)
            and s.body[0].exc.func.id == "GateSpecError")


SIMPLE = (ast.Assign, ast.AugAssign, ast.AnnAssign, ast.Expr, ast.Pass, ast.Delete, ast.Global, ast.Nonlocal,
          ast.Return, ast.Raise, ast.Break, ast.Continue)
_CMP_SWAP = {ast.Is: ast.Eq, ast.Eq: ast.Is, ast.IsNot: ast.NotEq, ast.NotEq: ast.IsNot}
_CMP2 = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE, ast.GtE: ast.Gt}
_IN = {ast.In: ast.NotIn, ast.NotIn: ast.In}


def _paths(root):
    """Every node under root with a path (a list of (field, index|None)) from root."""
    out = []

    def rec(n, path):
        out.append((n, path))
        for f, v in ast.iter_fields(n):
            if isinstance(v, list):
                for i, x in enumerate(v):
                    if isinstance(x, ast.AST):
                        rec(x, path + [(f, i)])
            elif isinstance(v, ast.AST):
                rec(v, path + [(f, None)])
    rec(root, [])
    return out


def _get(root, path):
    n = root
    for f, i in path:
        n = getattr(n, f) if i is None else getattr(n, f)[i]
    return n


def _set(root, path, new):
    parent = _get(root, path[:-1])
    f, i = path[-1]
    if i is None:
        setattr(parent, f, new)
    else:
        getattr(parent, f)[i] = new


def _is_type_call(x):
    return isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id == "type" and len(x.args) == 1


def sites(root):
    """-> [(op, desc, fn(copy))]: every operator application in root (a Region node)."""
    res = []
    body_owner = root if hasattr(root, "body") and isinstance(getattr(root, "body"), list) else None
    for n, path in _paths(root):
        # statement-level
        for f in ("body", "orelse", "finalbody"):
            v = getattr(n, f, None)
            if not (isinstance(v, list) and v and isinstance(v[0], ast.stmt)):
                continue
            for i, s in enumerate(v):
                if isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and type(s.value.value) is str and i == 0:
                    continue                                  # a docstring is not a statement of the code
                p = path + [(f, i)]
                res.append(("O1", f"delete line {s.lineno} ({type(s).__name__})",
                            lambda c, p=p: _set(c, p, ast.Pass())))
                if isinstance(s, ast.Break):
                    res.append(("O11", f"delete the break at line {s.lineno}", lambda c, p=p: _set(c, p, ast.Pass())))
                if i + 1 < len(v):
                    t = v[i + 1]
                    if isinstance(s, SIMPLE) and isinstance(t, SIMPLE):
                        def sw(c, n_path=path, f=f, i=i):
                            lst = getattr(_get(c, n_path), f)
                            lst[i], lst[i + 1] = lst[i + 1], lst[i]
                        res.append(("O8", f"swap lines {s.lineno} and {t.lineno}", sw))
                    if _is_raise_gse(s) and _is_raise_gse(t):
                        def sw14(c, n_path=path, f=f, i=i):
                            lst = getattr(_get(c, n_path), f)
                            lst[i], lst[i + 1] = lst[i + 1], lst[i]
                        res.append(("O14", f"swap the refusals at lines {s.lineno} and {t.lineno}", sw14))
        # O13: the innermost statement holding a coded literal
        if isinstance(n, ast.stmt) and path and _has_coded_literal(n):
            inner = any(isinstance(y, ast.stmt) and y is not n and _has_coded_literal(y) for y in ast.walk(n))
            if not inner:
                res.append(("O13", f"refusal deleted at line {n.lineno}", lambda c, p=path: _set(c, p, ast.Pass())))
        # tests
        if isinstance(n, (ast.If, ast.While, ast.IfExp, ast.Assert)):
            tp = path + [("test", None)]
            res.append(("O2", f"negate the test at line {n.lineno}",
                        lambda c, tp=tp: _set(c, tp, ast.UnaryOp(ast.Not(), _get(c, tp)))))
            for val in (True, False):
                res.append(("IF", f"the test at line {n.lineno} -> {val}",
                            lambda c, tp=tp, val=val: _set(c, tp, ast.Constant(val))))
        if isinstance(n, ast.BoolOp):
            for j in range(len(n.values)):
                def drop(c, p=path, j=j):
                    b = _get(c, p)
                    vals = b.values[:j] + b.values[j + 1:]
                    _set(c, p, vals[0] if len(vals) == 1 else ast.BoolOp(b.op, vals))
                res.append(("O3", f"drop operand {j} of the {type(n.op).__name__} at line {n.lineno}", drop))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("any", "all"):
            other = "all" if n.func.id == "any" else "any"
            res.append(("QUANT", f"{n.func.id} -> {other} at line {n.lineno}",
                        lambda c, p=path + [("func", None)], o=other: _set(c, p, ast.Name(o, ast.Load()))))
        if isinstance(n, ast.Compare):
            for j, op in enumerate(n.ops):
                for tab, name in ((_CMP_SWAP, "O4"), (_CMP2, "CMP"), (_IN, "O6")):
                    if type(op) in tab:
                        def cmp(c, p=path, j=j, new=tab[type(op)]):
                            _get(c, p).ops[j] = new()
                        res.append((name, f"{type(op).__name__} -> {tab[type(op)].__name__} at line {n.lineno}", cmp))
            # O5: exact type <-> isinstance/issubclass
            if len(n.ops) == 1 and type(n.ops[0]) in (ast.Is, ast.IsNot) and _is_type_call(n.left):
                def to_isinst(c, p=path):
                    x = _get(c, p)
                    call = ast.Call(ast.Name("isinstance", ast.Load()), [x.left.args[0], x.comparators[0]], [])
                    _set(c, p, call if isinstance(x.ops[0], ast.Is) else ast.UnaryOp(ast.Not(), call))
                res.append(("O5", f"exact type -> isinstance at line {n.lineno}", to_isinst))
            # O9: d.setdefault(k, v) is v -> an unconditional store
            if (len(n.ops) == 1 and type(n.ops[0]) in (ast.Is, ast.IsNot) and isinstance(n.left, ast.Call)
                    and isinstance(n.left.func, ast.Attribute) and n.left.func.attr == "setdefault"
                    and len(n.left.args) == 2):
                def claim(c, p=path):
                    x = _get(c, p)
                    d, (k, v) = x.left.func.value, x.left.args
                    store = ast.Call(ast.Attribute(d, "__setitem__", ast.Load()), [k, v], [])
                    _set(c, p, ast.Compare(store, [ast.Is() if isinstance(x.ops[0], ast.Is) else ast.IsNot()],
                                           [ast.Constant(None)]))
                res.append(("O9", f"setdefault claim -> unconditional store at line {n.lineno}", claim))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("isinstance", "issubclass") \
                and len(n.args) == 2:
            def to_exact(c, p=path, fn=n.func.id):
                x = _get(c, p)
                a0 = x.args[0]
                if fn == "issubclass":
                    left = a0
                else:
                    left = ast.Call(ast.Name("type", ast.Load()), [a0], [])
                _set(c, p, ast.Compare(left, [ast.Is()], [x.args[1]]))
            res.append(("O5", f"{n.func.id} -> exact type at line {n.lineno}", to_exact))
        # constants
        if isinstance(n, ast.Constant) and type(n.value) is int and not isinstance(n.value, bool):
            for d in (1, -1):
                res.append(("O7", f"int {n.value} -> {n.value + d} at line {getattr(n, 'lineno', '?')}",
                            lambda c, p=path, d=d: _set(c, p, ast.Constant(_get(c, p).value + d))))
        if isinstance(n, ast.Constant) and type(n.value) is float:
            for f in (0.5, 2.0):
                res.append(("O7b", f"float {n.value} x{f} at line {getattr(n, 'lineno', '?')}",
                            lambda c, p=path, f=f: _set(c, p, ast.Constant(_get(c, p).value * f))))
        # scope
        if isinstance(n, (ast.For, ast.AsyncFor)):
            ip = path + [("iter", None)]
            for lo, hi, lab in ((None, 1, "[:1]"), (-1, None, "[-1:]")):
                def it(c, ip=ip, lo=lo, hi=hi):
                    sl = ast.Slice(None if lo is None else ast.Constant(lo), None if hi is None else ast.Constant(hi))
                    _set(c, ip, ast.Subscript(ast.Call(ast.Name("list", ast.Load()), [_get(c, ip)], []), sl, ast.Load()))
                res.append(("O10", f"for-iter {lab} at line {n.lineno}", it))
        if isinstance(n, ast.Slice) and n.lower is not None and n.upper is None and n.step is None:
            def sl(c, p=path):
                x = _get(c, p)
                x.upper = ast.BinOp(copy.deepcopy(x.lower), ast.Add(), ast.Constant(1))
            res.append(("SLICE", f"[a:] -> [a:a+1] at line {getattr(n, 'lineno', '?')}", sl))
    return res


# ---------------------------------------------------------------------------------------------------
# mutants, TCE
# ---------------------------------------------------------------------------------------------------
def render(src_lines, node, new):
    ind = " " * node.col_offset
    first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
    txt = textwrap.indent(ast.unparse(ast.fix_missing_locations(new)), ind)
    return "".join(src_lines[:first - 1]) + txt + "\n" + "".join(src_lines[node.end_lineno:])


def code_sig(c):
    """The TCE comparison: bytecode, names, consts (recursively), flags, counts, variable names."""
    consts = tuple(code_sig(k) if isinstance(k, types.CodeType) else (type(k).__name__, repr(k)) for k in c.co_consts)
    return (c.co_code, c.co_names, consts, c.co_flags, c.co_argcount, c.co_kwonlyargcount,
            c.co_posonlyargcount, c.co_varnames, c.co_freevars, c.co_cellvars, c.co_name,
            getattr(c, "co_qualname", c.co_name), c.co_exceptiontable if hasattr(c, "co_exceptiontable") else b"")


def generate(impl):
    src = open(impl, encoding="utf-8").read()
    lines = src.splitlines(keepends=True)
    mod = load(impl)
    tree, reg, missing = region(src, mod)
    base = code_sig(compile(src, impl, "exec"))
    out = []
    for label, node in reg:
        for k, (op, desc, fn) in enumerate(sites(node)):
            c = copy.deepcopy(node)
            try:
                fn(c)
                msrc = render(lines, node, c)
                code = compile(msrc, impl, "exec")
            except (SyntaxError, ValueError, TypeError, IndexError, AttributeError) as e:
                out.append({"id": f"{label}#{k}", "region": label, "op": op, "family": FAMILY[op], "desc": desc,
                            "status": "NOT_COMPILED", "error": f"{type(e).__name__}: {e}"})
                continue
            tce = code_sig(code) == base
            out.append({"id": f"{label}#{k}", "region": label, "op": op, "family": FAMILY[op], "desc": desc,
                        "status": "TCE" if tce else "MUTANT", "src": None if tce else msrc})
    return out, [l for l, _ in reg], missing


# ---------------------------------------------------------------------------------------------------
# instruments
# ---------------------------------------------------------------------------------------------------
def _env():
    env = dict(os.environ)
    if DEPS:
        env["V5F_DEPS_PATH"] = DEPS
    return env


def inst_a(py, path):
    """The exam in mutation mode, --mutation ALL, twice; detected iff both runs fail (disagreement: NONREPRODUCIBLE)."""
    outs = []
    for _ in range(2):
        try:
            r = subprocess.run([py, os.path.join(HERE, "run_protocol_v5f_exam.py"), "--impl", path, "--mutation", "ALL"],
                               capture_output=True, text=True, timeout=7200, env=_env())
        except subprocess.TimeoutExpired:
            outs.append(("TIMEOUT", []))
            continue
        ln = [x for x in r.stdout.splitlines() if x.startswith("MUTATION_RESULT ")]
        if not ln:
            outs.append(("NOIMPORT" if "Error" in r.stderr else "CRASH", []))
            continue
        d = json.loads(ln[-1].split(" ", 1)[1])
        failed = sorted(c for c, x in d["results"].items() if not (x["ok"] and not x["leftover"]))
        outs.append(("FAIL" if failed else "PASS", failed))
    v = {o[0] != "PASS" for o in outs}
    if len(v) > 1:
        return "NONREPRODUCIBLE", outs
    return ("DETECTED" if v.pop() else "PASS"), outs


def inst_b(py, path):
    fd = path + ".sweep.json"
    subprocess.run([py, os.path.join(HERE, "crash_sweep_v5f.py"), "--impl", path, "--stride", "3", "--out", fd],
                   capture_output=True, text=True, timeout=14400, env=_env())
    try:
        d = json.load(open(fd))
    except (OSError, ValueError):
        return "DETECTED", "the sweep produced no result"
    return ("PASS" if d.get("G_FI") == "PASS" else "DETECTED"), d.get("G_FI")


def inst_c(py, path):
    fd = path + ".fuzz.json"
    subprocess.run([py, os.path.join(HERE, "fuzz_v5f.py"), "--impl", path, "--out", fd],
                   capture_output=True, text=True, timeout=14400, env=_env())
    try:
        d = json.load(open(fd))
    except (OSError, ValueError):
        return "DETECTED", "the fuzzer produced no result"
    return ("PASS" if d.get("verdict") == "PASS" else "DETECTED"), {k: d.get(k) for k in ("equality_diffs", "envelope_violations", "crashes")}


def inst_d(py, path, base, mask):
    fd = path + ".probe.json"
    subprocess.run([py, os.path.join(HERE, "diffprobe_v5f.py"), "--probe", "--impl", path, "--base", base,
                    "--mask", mask, "--out", fd], capture_output=True, text=True, timeout=28800, env=_env())
    try:
        d = json.load(open(fd))
    except (OSError, ValueError):
        return "DETECTED", "the probe produced no result"
    return ("DETECTED" if d.get("detected") else "PASS"), dict(list(d.get("flagged", {}).items())[:5])


def classify(py, path, base, mask, which):
    ev = {}
    try:
        r = subprocess.run([py, "-c", f"import importlib.util as u;s=u.spec_from_file_location('m',{path!r});"
                                      f"m=u.module_from_spec(s);s.loader.exec_module(m)"],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return "KILLED", {"import": r.stderr.strip().splitlines()[-1:]}
    except subprocess.TimeoutExpired:
        return "KILLED", {"import": "timeout"}
    for k, f in (("a", inst_a), ("b", inst_b), ("c", inst_c)):
        if k not in which:
            continue
        v, why = f(py, path)
        ev[k] = [v, why]
        if v == "DETECTED":
            return "KILLED", ev
    if "d" in which:
        v, why = inst_d(py, path, base, mask)
        ev["d"] = [v, why]
        if v == "DETECTED":
            return "EXAM_HOLE", ev
    return "UNDISTINGUISHED", ev


def main():
    if "--list" in ARGV or "--write" in ARGV:
        muts, reg, missing = generate(IMPL)
        per = {}
        for m in muts:
            f = per.setdefault(m["family"], {})
            f.setdefault(m["op"], {"MUTANT": 0, "TCE": 0, "NOT_COMPILED": 0})[m["status"]] += 1
        summary = {"impl": IMPL, "region": reg, "region_missing": missing, "mutants": len(muts), "per_family": per,
                   "families_without_mutants": [f for f in FAMILIES if not any(
                       v["MUTANT"] for v in per.get(f, {}).values())]}
        if "--write" in ARGV:
            d = _opt("--write")
            os.makedirs(d, exist_ok=True)
            index = []
            for i, m in enumerate(muts):
                e = {k: v for k, v in m.items() if k != "src"}
                if m["status"] == "MUTANT":
                    e["file"] = f"m{i:05d}.py"
                    open(os.path.join(d, e["file"]), "w", encoding="utf-8").write(m["src"])
                index.append(e)
            json.dump({"summary": summary, "mutants": index}, open(os.path.join(d, "index.json"), "w"), indent=1)
        print(json.dumps(summary, indent=1))
        return 0
    if "--run" in ARGV:
        d = _opt("--run")
        idx = json.load(open(os.path.join(d, "index.json")))
        only = set(_opt("--only").split(",")) if _opt("--only") else None
        which = _opt("--instruments", "abcd")
        base = os.path.abspath(_opt("--base", IMPL))
        out = _opt("--out")                         # JSON lines, one per mutant; a rerun skips finished ids
        done = set()
        if os.path.exists(out):
            for ln in open(out):
                try:
                    done.add(json.loads(ln)["id"])
                except ValueError:
                    pass
        for e in idx["mutants"]:
            if e["status"] != "MUTANT" or (only and e["id"] not in only and e.get("file") not in only):
                continue
            if e["id"] in done:
                continue
            t0 = time.monotonic()
            cls, ev = classify(sys.executable, os.path.join(os.path.abspath(d), e["file"]), base, _opt("--mask"), which)
            r = {**e, "python": sys.version.split()[0], "instruments": which, "class": cls, "evidence": ev,
                 "seconds": round(time.monotonic() - t0, 1)}
            with open(out, "a") as fh:
                fh.write(json.dumps(r, default=str) + "\n")
            print(e["id"], e["op"], cls, flush=True)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
