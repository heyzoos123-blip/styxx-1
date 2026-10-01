"""refcensus_v5f.py: G_REF (refusal deletion by coded literal) and G_HYG (hygiene and back-edge lint).

Written by the exam author from the design text (G_SEM "SM2" O13 and Gate, "Companion gates" G_HYG and its
step controls, M1, M2, M7, M10). Static except for importing the implementation once to read
_v5_faultpoints() (the region is defined by name, M10).

  python refcensus_v5f.py --impl PATH [--out RESULT.json]            the census and the lint on PATH
  python refcensus_v5f.py --impl PATH --controls                      also the step controls K11, K12,
                                                                      K12b, K13, K14 (each must be rejected)

G_REF's census (revision 13, GAP-50: over the whole module):
  - every coded literal (a str constant, or an f-string part, containing "[V5:"; docstrings and bare strings
    excluded) in the module, with its innermost enclosing statement (O13's site). The site is *mutable* iff
    its replacement by `pass` compiles; a literal outside a mutable site has no compiling O13 mutant. The
    census verdict is PASS iff there is none, and no blind shape. Units outside SM2's Region (the DECL and
    SECTION_DECL raises of Experiment.__init__, the module-level _CODE_RE) are counted like the others;
  - coded emissions in a blind shape (G_HYG's first clause; revision 13, GAP-51): a code no single literal
    holds whole: "[V5" split from ":" (or joined by +), a code prefix from str.format, %-formatting or
    joining, and a code from an f-string's formatted value. --controls plants each (all must be flagged),
    and positive control #5's 8 shapes of mutation_gate_blindspots.json (spec data), which O13 must delete
    by their literal.
  G_REF's kill test (100% of O13 mutants KILLED by the frozen exam) is `--o13-mutants DIR`, which writes one
  patched copy per site for the runner's mutation mode, and `--o13-kill DIR --journal J.jsonl [--deps DIR]`, which
  writes them and runs each in the frozen runner's mutation mode (resumable through the journal):
    1. the cases whose row or body names the deleted literal's code, in one `--mutation ALL --only ...` run;
       if none names it, or none fails, every case (`--mutation ALL`);
    2. a second run of the failing cases (or of every case, if the first was a crash or a timeout);
    KILLED iff both runs detect it (a failing case, a runner crash, or the driver's timeout, each recorded as
    such), NONREPRODUCIBLE if only the first does, SURVIVED if none does.
"""
import ast, dis, hashlib, importlib.util, json, os, re, sys, types

HERE = os.path.dirname(os.path.abspath(__file__))
SCORING = ("Experiment._check_coverage", "Experiment.check_metrics", "Experiment.score", "_check_trace_shape",
           "_finite")
CLASSES = ("_Mint", "_Core", "_Opening", "_Txn", "_CoverageTracer")
V4_ERA = ("undeclared_power_gates", "_select_gates_block", "PrologueError", "GateSpecError", "Verdict",
          "_resolve", "Experiment")
STEPS = ("_unwind_on", "_unwind_off", "_take", "_register", "_set_local")
NO_BACKEDGE = ("_commit", "_detach", "_unwind_on", "_unwind_off", "_take", "_register", "_set_local", "_named")
EVENTS_OK = {"PY_START", "PY_RESUME", "PY_RETURN", "PY_YIELD", "PY_UNWIND"}
EVENTS_ALL = EVENTS_OK | {"INSTRUCTION", "LINE", "JUMP", "BRANCH", "BRANCH_LEFT", "BRANCH_RIGHT", "CALL",
                          "C_RETURN", "C_RAISE", "RAISE", "RERAISE", "EXCEPTION_HANDLED", "STOP_ITERATION",
                          "PY_THROW"}
# M7 / G_HYG (revision 8, M3): the frozen per-step bindings of statement 1
STEP_BIND = {
    "_unwind_on": {"t": ("TOOL",), "get_tool": ("MON", 0), "get_events": ("MON", 1), "set_events": ("MON", 2)},
    "_unwind_off": {"t": ("TOOL",), "get_tool": ("MON", 0), "set_events": ("MON", 2)},
    "_take": {"get_tool": ("MON", 0), "use_tool_id": ("MON", 5)},
    "_register": {"get_tool": ("MON", 0), "register_callback": ("MON", 4)},
    "_set_local": {"get_tool": ("MON", 0), "set_local_events": ("MON", 3)},
}
VOCAB = {"_map", "_chain", "_compress", "_filter", "_is", "_not", "_and", "_setitem", "_ARMED", "_FLAGS",
         "_VALUES", "_CONSUME", "_LOST_KEY", "_TRUE", "_PYU1", "_ZERO1", "_NONE1", "_NAME1", "_repeat", "_list",
         "_EVENTS5", "_CALLBACKS5", "_TOOL_NAME", "_is_not", "_LOST_APPEND", "_tee"}
ONLY_REGISTER = {"_is_not", "_LOST_APPEND", "_tee"}
PARAMS = {"o", "key", "t", "code", "events"}
MON_WRITERS = {2: "set_events", 3: "set_local_events", 4: "register_callback", 5: "use_tool_id"}
RELOAD_GET = ("_BY_FN", "_MINTED", "_ANCHORS", "_CUT", "_GUARD", "_TOOL", "_HANDLE_DICT", "_LOOP_DICT", "_LOST",
              "_MON", "_get_running_loop")
OPENING_FIELDS = ("core", "section", "frame", "tid", "loop", "calls", "ambiguous", "fin", "lazy", "armed")
CORE_FIELDS = ("exp", "marks", "by_code", "names", "sections", "openings", "problems", "clone_called",
               "uncredited", "lost_note", "flags", "facade", "pid", "prov", "lost0")


def load(path, name="v5f_impl_census"):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


class Region:
    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.src = open(path, encoding="utf-8").read()
        self.tree = ast.parse(self.src)
        self.mod = load(path)
        self.fp = self.mod._v5_faultpoints()
        self.funcs = {}                                       # qualname -> FunctionDef
        for n in self.tree.body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.funcs[n.name] = n
            elif isinstance(n, ast.ClassDef):
                for m in n.body:
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self.funcs[f"{n.name}.{m.name}"] = m
        self.machinery = [k for k in self.fp if k in self.funcs]
        self.region = self.machinery + [k for k in SCORING if k in self.funcs]
        self.codes = dict(self.fp)
        for q in SCORING:
            obj = self.mod
            for part in q.split("."):
                obj = getattr(obj, part)
            self.codes[q] = obj.__code__

    def nodes(self, names=None):
        for k in (names or self.region):
            if k in self.funcs:
                for n in ast.walk(self.funcs[k]):
                    yield k, n


def _dotted(n):
    parts = []
    while isinstance(n, ast.Attribute):
        parts.append(n.attr)
        n = n.value
    if isinstance(n, ast.Name):
        parts.append(n.id)
        return ".".join(reversed(parts))
    return None


def _mon_index(n):
    """_MON[0][i] -> i, else None."""
    if (isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) and isinstance(n.value, ast.Subscript)
            and isinstance(n.value.value, ast.Name) and n.value.value.id == "_MON"
            and isinstance(n.value.slice, ast.Constant) and n.value.slice.value == 0):
        return n.slice.value
    return None


# ---------------------------------------------------------------------------------------------------
# G_REF: the coded-literal census
# ---------------------------------------------------------------------------------------------------
_O13_COMPILES = {}


def _o13_compiles(R, a, b):
    key = (id(R), a, b)
    if key not in _O13_COMPILES:
        lines = R.src.split("\n")
        first = lines[a - 1]
        indent = first[:len(first) - len(first.lstrip())]
        new = lines[:a - 1] + [indent + "pass"] + [""] * (b - a) + lines[b:]
        try:
            compile("\n".join(new), "<o13>", "exec")
            _O13_COMPILES[key] = True
        except SyntaxError:
            _O13_COMPILES[key] = False
    return _O13_COMPILES[key]


def census(R):
    parents = {}
    for p in ast.walk(R.tree):
        for c in ast.iter_child_nodes(p):
            parents[c] = p
    region_nodes = {id(n): k for k, fn in ((k, R.funcs[k]) for k in R.region) for n in ast.walk(fn)}
    sites, outside, blind = [], [], []
    for n in ast.walk(R.tree):
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            s = n.value
            joined = isinstance(parents.get(n), ast.JoinedStr)
            if "[V5:" in s:
                st = n
                while not isinstance(st, ast.stmt):
                    st = parents[st]
                fn = region_nodes.get(id(n))
                if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and st.value is n:
                    continue                                   # docstrings and bare strings emit nothing
                site = {"line": n.lineno, "stmt_line": st.lineno, "stmt_end": st.end_lineno, "func": fn,
                        "code": (re.search(r"\[V5:([A-Z_]*)", s) or [None, ""])[1], "fstring": joined}
                # revision 13 (GAP-50): every coded literal of the module; a *mutable site* is its innermost
                # statement whose replacement by `pass` compiles; outside one, O13 has no compiling mutant
                (sites if _o13_compiles(R, st.lineno, st.end_lineno) else outside).append(site)
            elif re.search(r"\[V5(?!:)|(?<!\[)V5:", s) and not (isinstance(parents.get(n), ast.Expr)):
                blind.append({"line": n.lineno, "shape": "a code prefix split across literals", "text": s[:40]})
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ("format", "join"):
            base = n.func.value
            if isinstance(base, ast.Constant) and isinstance(base.value, str) and re.search(r"\[V5|\{", base.value) \
                    and "[V5" in base.value and "[V5:" not in base.value:
                blind.append({"line": n.lineno, "shape": f"str.{n.func.attr}", "text": base.value[:40]})
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod) and isinstance(n.left, ast.Constant) \
                and isinstance(n.left.value, str) and "[V5" in n.left.value and re.search(r"\[V5:%", n.left.value):
            blind.append({"line": n.lineno, "shape": "%-formatted code", "text": n.left.value[:40]})
        if isinstance(n, ast.JoinedStr):
            parts = [v for v in n.values]
            for a, b in zip(parts, parts[1:]):
                if isinstance(a, ast.Constant) and isinstance(a.value, str) and a.value.endswith("[V5:") \
                        and isinstance(b, ast.FormattedValue):
                    blind.append({"line": n.lineno, "shape": "code from a formatted value", "text": a.value[-8:]})
    return {"sites": sites, "outside_mutable_site": outside, "blind": blind}


def o13_mutants(R, outdir):
    """One patched copy per O13 site: the innermost enclosing statement of the coded literal becomes pass."""
    lines = R.src.split("\n")
    os.makedirs(outdir, exist_ok=True)
    seen, made = set(), []
    for s in census(R)["sites"]:
        key = (s["stmt_line"], s["stmt_end"])
        if key in seen:
            continue
        seen.add(key)
        first = lines[s["stmt_line"] - 1]
        indent = first[:len(first) - len(first.lstrip())]
        new = lines[:s["stmt_line"] - 1] + [indent + "pass"] + [""] * (s["stmt_end"] - s["stmt_line"]) + lines[s["stmt_end"]:]
        name = f"o13_L{s['stmt_line']}"
        d = os.path.join(outdir, name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "ref_v5f.py"), "w") as fh:
            fh.write("\n".join(new))
        made.append({"name": name, "stmt_line": s["stmt_line"], "code": s["code"], "func": s["func"]})
    return made


def _case_text(runner):
    """{case id: its row and the source of its body and of the --sub body of the same id} from the runner's
    text (the v5e-ported cases are not in it: a code they alone witness falls back to every case)."""
    src = open(runner, encoding="utf-8").read()
    tree = ast.parse(src)
    cases, subs = {}, {}
    for n in tree.body:
        if not isinstance(n, ast.FunctionDef):
            continue
        for d in n.decorator_list:
            if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.args and isinstance(d.args[0], ast.Constant):
                key = d.args[0].value
                text = ast.get_source_segment(src, n) + " " + " ".join(
                    a.value for a in d.args if isinstance(a, ast.Constant) and isinstance(a.value, str))
                if d.func.id == "case":
                    cases[key] = cases.get(key, "") + " " + text
                elif d.func.id == "sub":
                    subs[key.split(":")[0]] = subs.get(key.split(":")[0], "") + " " + text
    return {c: t + " " + subs.get(c, "") for c, t in cases.items()}


def _mutation_run(py, runner, impl, cases, deps, timeout):
    import subprocess
    import v5f_tmp
    env = dict(os.environ)
    if deps:
        env["V5F_DEPS_PATH"] = deps
    cmd = [py, runner, "--impl", impl, "--mutation", "ALL"] + (["--only", ",".join(cases)] if cases else [])
    v5f_tmp.disk_guard(what=impl)
    try:
        r = v5f_tmp.child_run(cmd, env=env, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        v5f_tmp.disk_guard(what=impl)
        return {"status": "TIMEOUT", "failed": [], "cases": len(cases) if cases else "ALL"}
    v5f_tmp.check_child(r.stderr, impl)
    ln = [x for x in r.stdout.splitlines() if x.startswith("MUTATION_RESULT ")]
    if not ln:
        return {"status": "CRASH", "failed": [], "cases": len(cases) if cases else "ALL",
                "why": (r.stderr.strip().splitlines() or ["?"])[-1][:200]}
    d = json.loads(ln[-1].split(" ", 1)[1])
    failed = sorted(c for c, x in d["results"].items() if not (x["ok"] and not x["leftover"]))
    return {"status": "FAIL" if failed else "PASS", "failed": failed, "cases": len(d["results"]),
            "detail": {c: d["results"][c]["detail"][:160] for c in failed[:3]}}


def o13_kill(impl, outdir, journal, deps=None):
    import v5f_tmp
    py = sys.executable
    runner = os.path.join(HERE, "run_protocol_v5f_exam.py")
    made = o13_mutants(Region(impl), outdir)
    text = _case_text(runner)
    done = set()
    if os.path.exists(journal):
        for ln in open(journal):
            try:
                d = json.loads(ln)
            except ValueError:
                continue
            if d.get("python") == sys.version.split()[0]:
                done.add(d["name"])
    for m in made:
        if m["name"] in done:
            continue
        path = os.path.join(outdir, m["name"], "ref_v5f.py")
        target = sorted(c for c, t in text.items() if m["code"] and m["code"] in t)
        runs = []
        r1 = _mutation_run(py, runner, path, target, deps, 1800) if target else None
        if r1 is None or r1["status"] == "PASS":
            if r1 is not None:
                runs.append(r1)
            r1 = _mutation_run(py, runner, path, None, deps, 3600)
        runs.append(r1)
        det1 = r1["status"] != "PASS"
        if det1:
            again = r1["failed"][:40] if r1["status"] == "FAIL" else None
            r2 = _mutation_run(py, runner, path, again, deps, 3600 if again is None else 1800)
            runs.append(r2)
            cls = "KILLED" if r2["status"] != "PASS" else "NONREPRODUCIBLE"
        else:
            cls = "SURVIVED"
        row = {"name": m["name"], "stmt_line": m["stmt_line"], "code": m["code"], "func": m["func"],
               "python": sys.version.split()[0], "targeted": len(target), "class": cls, "runs": runs}
        with open(journal, "a") as fh:
            fh.write(json.dumps(row) + "\n")
        print(m["name"], m["code"], cls, [(x["status"], x["cases"], x["failed"][:3]) for x in runs], flush=True)
    rows = [json.loads(ln) for ln in open(journal) if ln.strip()]
    rows = [r for r in rows if r["python"] == sys.version.split()[0]]
    names = {m["name"] for m in made}
    rows = [r for r in rows if r["name"] in names]
    out = {"python": sys.version.split()[0], "impl": impl, "mutants": len(made), "decided": len(rows),
           "killed": sum(r["class"] == "KILLED" for r in rows),
           "not_killed": sorted(r["name"] for r in rows if r["class"] != "KILLED"),
           "by_status": {r["name"]: r["runs"][-1]["status"] for r in rows if r["runs"][-1]["status"] != "FAIL"}}
    out["G_REF_kill"] = "PASS" if out["decided"] == out["mutants"] and out["killed"] == out["mutants"] else "FAIL"
    return out


# ---------------------------------------------------------------------------------------------------
# G_HYG
# ---------------------------------------------------------------------------------------------------
def hyg(R):
    V = []

    def bad(clause, where, what):
        V.append({"clause": clause, "where": where, "what": what})

    # 1. coded emissions in a blind shape
    for b in census(R)["blind"]:
        bad("blind shape", f"line {b['line']}", b["shape"])
    # 2. no with, no threading lock, no try/finally except _run's and _run_async's single one
    for k, n in R.nodes(R.machinery):
        if isinstance(n, (ast.With, ast.AsyncWith)):
            bad("no with", k, f"line {n.lineno}")
        if isinstance(n, ast.Try) and n.finalbody and k not in ("_run", "_run_async"):
            bad("no try/finally", k, f"line {n.lineno}")
        d = _dotted(n) if isinstance(n, ast.Attribute) else None
        if d and re.match(r"threading\.(Lock|RLock|Condition|Semaphore|BoundedSemaphore|Event|Barrier)$", d):
            bad("no threading lock", k, d)
    for k in ("_run", "_run_async"):
        tries = [n for n in ast.walk(R.funcs[k]) if isinstance(n, ast.Try)]
        fin = [t for t in tries if t.finalbody]
        if len(fin) != 1 or len(tries) != 1:
            bad("exactly one try/finally", k, f"{len(tries)} try, {len(fin)} with finally")
            continue
        t = fin[0]
        if t.handlers or t.orelse:
            bad("try/finally only", k, "handlers or else")
        body = t.body
        ok = (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Call)
              and _dotted(body[0].value.func) == "_commit")
        for st in body[1:]:
            if isinstance(st, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                continue
            if isinstance(st, ast.Expr) and isinstance(st.value, (ast.Call, ast.Await)):
                continue
            ok = False
        calls = [n for st in body[1:] for n in ast.walk(st) if isinstance(n, ast.Call)]
        awaits = [n for st in body for n in ast.walk(st) if isinstance(n, ast.Await)]
        if k == "_run_async" and len(awaits) != 1:
            ok = False
        if not ok:
            bad("try body shape", k, ast.unparse(ast.Module(body=body, type_ignores=[]))[:160])
        fb = t.finalbody
        want = ["_detach(o, (end, ()))", "o.frame = None"]
        if [ast.unparse(s) for s in fb] != want:
            bad("finally shape", k, [ast.unparse(s) for s in fb])
    # 3. no loop in any try body; no backward jump in the step and close functions; reachable functions
    for k, n in R.nodes(R.machinery):
        if isinstance(n, ast.Try):
            for st in n.body:
                for x in ast.walk(st):
                    if isinstance(x, (ast.For, ast.While, ast.AsyncFor, ast.comprehension)):
                        bad("no loop in a try body", k, f"line {x.lineno if hasattr(x, 'lineno') else n.lineno}")
    for k in NO_BACKEDGE:
        if k in R.fp:
            back = [i.offset for i in dis.get_instructions(R.fp[k]) if "BACKWARD" in i.opname]
            if back:
                bad("no backward jump", k, back)
    reach, todo = set(), []
    for k in ("_run", "_run_async"):
        t = [n for n in ast.walk(R.funcs[k]) if isinstance(n, ast.Try)]
        for st in (t[0].body + t[0].finalbody if t else []):
            for x in ast.walk(st):
                if isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id in R.funcs:
                    todo.append(x.func.id)
    while todo:
        k = todo.pop()
        if k in reach:
            continue
        reach.add(k)
        for x in ast.walk(R.funcs[k]):
            if isinstance(x, ast.Call) and isinstance(x.func, ast.Name) and x.func.id in R.funcs:
                todo.append(x.func.id)
    for k in sorted(reach):
        if k in R.fp and any("BACKWARD" in i.opname for i in dis.get_instructions(R.fp[k])):
            bad("no loop reachable from a try body or finally", k, "backward jump")
    # 4. no nested code objects
    for k, c in R.codes.items():
        if any(isinstance(x, types.CodeType) for x in c.co_consts):
            bad("no nested code object", k, [x.co_name for x in c.co_consts if isinstance(x, types.CodeType)])
    # 5. except clauses
    for k, n in R.nodes():
        if not isinstance(n, ast.Try):
            continue
        for h in n.handlers:
            ty = ast.unparse(h.type) if h.type is not None else "<bare>"
            if k == "_exit" and ty == "GateSpecError":
                continue
            if k == "_resolve_target" and any(isinstance(x, ast.Raise) and x.cause is not None for x in ast.walk(h)):
                continue
            if k == "Experiment.check_metrics" and ty == "GateSpecError":
                continue
            if k in ("_finite", "Experiment.score") and ty == "OverflowError":
                continue
            bad("no except", k, f"line {h.lineno}: except {ty}")
    ex = [h for n in ast.walk(R.funcs["_exit"]) if isinstance(n, ast.Try) for h in n.handlers]
    if len(ex) != 2:
        bad("_exit's two except GateSpecError", "_exit", len(ex))
    ch = [h for n in ast.walk(R.funcs["_resolve_target"]) if isinstance(n, ast.Try) for h in n.handlers
          if any(isinstance(x, ast.Raise) and x.cause is not None for x in ast.walk(h))]
    if len(ch) != 2:
        bad("the two chained user-code sites", "_resolve_target", len(ch))
    # 6. imports
    for k, n in R.nodes(R.machinery):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module]
            if not (k == "coverage_trace" and names == ["asyncio"]):
                bad("no import", k, names)
        if isinstance(n, ast.Call):
            d = _dotted(n.func) or ""
            if d == "__import__" or d.startswith("importlib"):
                if not (k == "_resolve_target" and d == "importlib.import_module"):
                    bad("no importlib call", k, d)
    imc = [n for n in ast.walk(R.funcs["_resolve_target"]) if isinstance(n, ast.Call) and _dotted(n.func) == "importlib.import_module"]
    if len(imc) != 1:
        bad("one importlib.import_module", "_resolve_target", len(imc))
    # 7. no type test by tuple membership
    for k, n in R.nodes():
        if isinstance(n, ast.Compare) and any(isinstance(o, (ast.In, ast.NotIn)) for o in n.ops):
            left_type = isinstance(n.left, ast.Call) and _dotted(n.left.func) == "type"
            right_types = any(isinstance(c, ast.Name) and c.id in ("_LAZY_TYPES",) for c in n.comparators)
            if left_type or right_types:
                bad("no type test by tuple membership", k, ast.unparse(n)[:80])
    # 8. no sys.monitoring event other than the five
    for k, n in R.nodes(R.machinery):
        name = n.attr if isinstance(n, ast.Attribute) else (n.id if isinstance(n, ast.Name) else None)
        if name in EVENTS_ALL - EVENTS_OK:
            bad("only the five events", k, name)
    # 9. the frozen set of function and class names
    allowed_top = set(V4_ERA) | set(CLASSES) | {k for k in R.fp if "." not in k} | {"_finite", "_check_trace_shape"}
    for n in R.tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name not in allowed_top:
            bad("frozen name set", "module", n.name)
    ct = [n for n in R.tree.body if isinstance(n, ast.ClassDef) and n.name == "_CoverageTracer"]
    if ct:
        meths = {m.name for m in ct[0].body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
        allowed = {k.split(".", 1)[1] for k in R.fp if k.startswith("_CoverageTracer.")}
        for m in meths - allowed:
            bad("frozen name set", "_CoverageTracer", m)
        if "__init__" in meths:
            bad("the facade has no __init__", "_CoverageTracer", "__init__")
    # 10. _forget_in_child writes __code__ only in its last loop; _detach pops anchors only through _unwind_off
    f = R.funcs["_forget_in_child"]
    loops = [s for s in f.body if isinstance(s, ast.For)]
    writes = [n for n in ast.walk(f) if isinstance(n, ast.Assign) and any(
        isinstance(t, ast.Attribute) and t.attr == "__code__" for t in n.targets)]
    if not loops or f.body[-1] is not loops[-1] or any(not any(w is x for x in ast.walk(loops[-1])) for w in writes):
        bad("_forget_in_child writes __code__ only in its last loop, last", "_forget_in_child", len(writes))
    d = R.funcs["_detach"]
    for n in ast.walk(d):
        if isinstance(n, ast.Call) and _dotted(n.func) in ("_ANCHORS.pop", "_ANCHORS.clear", "_ANCHORS.popitem"):
            bad("_detach pops only through _unwind_off", "_detach", ast.unparse(n))
        if isinstance(n, ast.Delete):
            bad("_detach pops only through _unwind_off", "_detach", ast.unparse(n))
    # 11. _commit's statements; _open stores no anchor and calls no _unwind_on; _unwind_on only from _commit
    c = R.funcs["_commit"].body
    c = [s for s in c if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
    ok = (len(c) == 4 and ast.unparse(c[0]) == "_ANCHORS[o.frame] = o" and isinstance(c[1], ast.If)
          and any(isinstance(x, ast.Raise) for x in ast.walk(c[1]))
          and any(isinstance(x, ast.Call) and _dotted(x.func) == "_detach" for x in ast.walk(c[1]))
          and ast.unparse(c[2]) == "_unwind_on(o)" and ast.unparse(c[3]) == "o.armed = True")
    if not ok:
        bad("_commit's statements", "_commit", [ast.unparse(s)[:50] for s in c])
    for n in ast.walk(R.funcs["_open"]):
        if isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Store) and _dotted(n.value) == "_ANCHORS":
            bad("_open stores no anchor", "_open", n.lineno)
    for k, n in R.nodes(R.machinery):
        if isinstance(n, ast.Call) and _dotted(n.func) == "_unwind_on" and k != "_commit":
            bad("_unwind_on only from _commit", k, n.lineno)
    # 12. the step functions
    for k in STEPS:
        V.extend(step_shape(R, k))
    # 13. _Opening and _Core
    for cls, fields in (("_Opening", OPENING_FIELDS), ("_Core", CORE_FIELDS)):
        node = [n for n in R.tree.body if isinstance(n, ast.ClassDef) and n.name == cls][0]
        body = [s for s in node.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
        ok = (len(body) == 2 and isinstance(body[0], ast.Assign) and ast.unparse(body[0].targets[0]) == "__slots__"
              and isinstance(body[0].value, ast.Tuple)
              and tuple(e.value for e in body[0].value.elts if isinstance(e, ast.Constant)) == fields
              and isinstance(body[1], ast.FunctionDef) and body[1].name == "__init__")
        if not ok:
            bad("class body is __slots__ and __init__ only", cls, [type(s).__name__ for s in body])
    # 14. sys.monitoring writers only in the steps; _retire; _reconcile's end; no waits outside _acquire
    for k, n in R.nodes(R.machinery):
        if isinstance(n, ast.Call):
            i = _mon_index(n.func)
            if i in MON_WRITERS and k != "_forget_in_child":
                bad("monitoring writers only in the steps", k, MON_WRITERS[i])
            if isinstance(n.func, ast.Name) and n.func.id in MON_WRITERS.values():
                binds = STEP_BIND.get(k, {})
                if n.func.id not in binds:
                    bad("each writer only in the steps that bind it", k, n.func.id)
            if _dotted(n.func) in ("_sleep",) and k != "_acquire":
                bad("no wait outside _acquire", k, "_sleep")
    for n in ast.walk(R.funcs["_retire"]):
        if isinstance(n, ast.Call) and _dotted(n.func) in ("_unwind_off", "_unwind_on"):
            bad("_retire has no step 6", "_retire", _dotted(n.func))
    rb = R.funcs["_reconcile"].body
    if not (len(rb) >= 2 and isinstance(rb[-2], ast.For) and ast.unparse(rb[-1]) ==
            "if _TOOL[0] is not None:\n    _unwind_off(None)"):
        bad("_reconcile ends with the prune, then _unwind_off(None)", "_reconcile", ast.unparse(rb[-1])[:60])
    for nm in ("_CLEARING", "_await_clearers"):
        if nm in R.mod.__dict__:
            bad("does not exist", "module", nm)
    # 15. o.frame writes; _detach's UNWIND_LOST test order
    for k, n in R.nodes(R.machinery):
        if isinstance(n, ast.Assign) and any(ast.unparse(t) == "o.frame" for t in n.targets):
            if k not in ("_open", "_run", "_run_async") and k != "_Opening.__init__":
                bad("o.frame assigned only in _open and the finally", k, n.lineno)
    ds = ast.unparse(R.funcs["_detach"])
    idx = [ds.find(x) for x in ("o.armed", "_MON[0][1]", "_ANCHORS.get(fr) is o", "_unwind_off(fr)")]
    if -1 in idx or idx != sorted(idx):
        bad("_detach's UNWIND_LOST test order", "_detach", idx)
    # 16. _TOOL_NAME only by identity; _named's test
    for k, n in R.nodes(R.machinery):
        if isinstance(n, ast.Compare) and any(isinstance(x, ast.Name) and x.id == "_TOOL_NAME"
                                              for x in [n.left] + n.comparators):
            if not all(isinstance(o, (ast.Is, ast.IsNot)) for o in n.ops):
                bad("_TOOL_NAME only by identity", k, ast.unparse(n))
    if ast.unparse(R.funcs["_named"].body[-1]) != "return _MON[0][0](i) is _TOOL_NAME":
        bad("_named's test", "_named", ast.unparse(R.funcs["_named"].body[-1]))
    # 17. the clock; 18. no profile or trace functions
    for k, n in R.nodes(R.machinery):
        d = _dotted(n) if isinstance(n, ast.Attribute) else None
        if d in ("time.monotonic", "time.sleep", "time.time", "time.perf_counter"):
            bad("the clock only through _monotonic and _sleep", k, d)
        if d and re.search(r"(^|\.)(setprofile|settrace|setprofile_all_threads|settrace_all_threads)$", d):
            bad("no profile or trace function", k, d)
        if isinstance(n, ast.Name) and n.id in ("setprofile", "settrace"):
            bad("no profile or trace function", k, n.id)
    # 19. reload bindings; _MON and _get_running_loop bound only in coverage_trace, in R9-4's order; _GUARD
    getb, plain = {}, []
    for n in R.tree.body:
        if isinstance(n, ast.Assign):
            for t in n.targets:
                names = [e.id for e in (t.elts if isinstance(t, ast.Tuple) else [t]) if isinstance(e, ast.Name)]
                src = ast.unparse(n.value)
                for nm in names:
                    if "globals().get" in src:
                        getb[nm] = src
    want = set(RELOAD_GET) | {"_TOOL_NAME"}
    if set(getb) != want:
        bad("exactly the reload names via globals().get", "module", sorted(set(getb) ^ want))
    if "_TOOL_NAME" in getb and not re.match(r"globals\(\)\.get\('_TOOL_NAME'\) or ", getb["_TOOL_NAME"].replace('"', "'")):
        bad("_TOOL_NAME via globals().get(...) or", "module", getb["_TOOL_NAME"][:60])
    for k, n in R.nodes(R.machinery):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                tt = ast.unparse(t)
                if tt in ("_MON[0]", "_get_running_loop") and k != "coverage_trace":
                    bad("_MON and _get_running_loop bound only in coverage_trace", k, tt)
    f = R.funcs["coverage_trace"]
    raises = [n.lineno for n in ast.walk(f) if isinstance(n, ast.Raise)]
    imp = [n.lineno for n in ast.walk(f) if isinstance(n, ast.Import) and any(a.name == "asyncio" for a in n.names)]
    binds = [n.lineno for n in ast.walk(f) if isinstance(n, ast.Assign) and any(
        ast.unparse(t) in ("_MON[0]", "_get_running_loop") for t in n.targets)]
    hd = [n.lineno for n in ast.walk(f) if isinstance(n, ast.Name) and n.id == "_HANDLE_DICT"]
    if not (binds and imp and hd and all(max(raises) < x and imp[0] < x < min(hd) for x in binds)):
        bad("R9-4 order in coverage_trace", "coverage_trace", {"raises": max(raises) if raises else None,
                                                                "import": imp, "binds": binds})
    body = R.tree.body
    ti = [i for i, n in enumerate(body) if isinstance(n, ast.ClassDef) and n.name == "_Txn"]
    if not ti or ast.unparse(body[ti[0] + 1]).replace('"', "'") != "if _GUARD is None:\n    _GUARD = {'hint': _Txn(None, 0, None)}":
        bad("_GUARD set by the statement after class _Txn", "module", ast.unparse(body[ti[0] + 1])[:60] if ti else None)
    # 20. get_local_events only in _exit_txn and _v5_state; sys.monitoring attributes only in coverage_trace
    for k, n in R.nodes(R.machinery):
        if _mon_index(n) == 6 and k not in ("_exit_txn", "_v5_state"):
            bad("_MON[0][6] only in _exit_txn and _v5_state", k, n.lineno)
        d = _dotted(n) if isinstance(n, ast.Attribute) else None
        if d and d.startswith("sys.monitoring") and k != "coverage_trace":
            bad("sys.monitoring read only in coverage_trace", k, d)
    for k in STEPS:
        for n in ast.walk(R.funcs[k]):
            if _mon_index(n) == 6:
                bad("no step binds index 6", k, n.lineno)
    return V


def step_shape(R, k):
    V = []

    def bad(clause, what):
        V.append({"clause": clause, "where": k, "what": what})

    f = R.funcs[k]
    body = [s for s in f.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))]
    n_want = 3 if k == "_register" else 2
    if len(body) != n_want:
        bad("statement count", len(body))
        return V
    s1 = body[0]
    ok = isinstance(s1, ast.Assign) and len(s1.targets) == 1
    names, vals = [], []
    if ok:
        t = s1.targets[0]
        names = [e.id for e in (t.elts if isinstance(t, ast.Tuple) else [t]) if isinstance(e, ast.Name)]
        vals = s1.value.elts if isinstance(s1.value, ast.Tuple) else [s1.value]
        ok = len(names) == len(vals)
    got = {}
    if ok:
        for nm, v in zip(names, vals):
            i = _mon_index(v)
            if i is not None:
                got[nm] = ("MON", i)
            elif ast.unparse(v) == "_TOOL[0]":
                got[nm] = ("TOOL",)
            else:
                got[nm] = ("OTHER", ast.unparse(v))
    if not ok or got != STEP_BIND[k]:
        bad("statement 1 binds exactly the frozen set", got)
    pipes = body[1:]
    if k == "_register":
        s2 = pipes[0]
        if not (isinstance(s2, ast.Assign) and ast.unparse(s2.targets[0]).strip("()") == "a, b"
                and isinstance(s2.value, ast.Call) and ast.unparse(s2.value.func) == "_tee"):
            bad("statement 2 is a, b = _tee(P)", ast.unparse(s2)[:60])
    last = pipes[-1]
    if k == "_register":
        ok = isinstance(last, ast.Return) and isinstance(last.value, ast.Call) and ast.unparse(last.value.func) == "_list"
    else:
        ok = isinstance(last, ast.Expr) and isinstance(last.value, ast.Call) and ast.unparse(last.value.func) == "_CONSUME"
    if not ok:
        bad("the consuming statement", ast.unparse(last)[:60])
    allowed = VOCAB | set(STEP_BIND[k]) | PARAMS | {"_ANCHORS", "None"} | ({"a", "b"} if k == "_register" else set())
    if k != "_register":
        allowed -= ONLY_REGISTER
    for st in pipes:
        for n in ast.walk(st):
            if isinstance(n, ast.Name) and n.id not in allowed and not (isinstance(n.ctx, ast.Store) and n.id in ("a", "b")):
                bad("pipeline vocabulary", n.id)
            if isinstance(n, (ast.Subscript, ast.Compare, ast.BoolOp, ast.UnaryOp, ast.BinOp, ast.IfExp,
                              ast.NamedExpr, ast.Starred, ast.Lambda, ast.GeneratorExp, ast.ListComp,
                              ast.SetComp, ast.DictComp)):
                bad("operator ban", type(n).__name__)
            if isinstance(n, ast.Attribute) and ast.unparse(n) not in ("o.frame", "_ANCHORS.get", "_ANCHORS.pop",
                                                                        "_chain.from_iterable"):
                bad("attribute reads", ast.unparse(n))
            if isinstance(n, ast.Call):
                fn = ast.unparse(n.func)
                if fn not in (VOCAB | set(STEP_BIND[k]) | {"_ANCHORS.get", "_ANCHORS.pop", "_chain.from_iterable"}):
                    bad("calls only of the vocabulary", fn)
    for n in ast.walk(f):
        if isinstance(n, ast.Name) and n.id == "_CALLBACKS5":
            pass
    return V


# ---------------------------------------------------------------------------------------------------
# G_HYG's step controls (revision 8, M2, M3): frozen patches the lint must reject
# ---------------------------------------------------------------------------------------------------
REG_OLD = """    a, b = _tee(_map(register_callback,
                     _compress(_repeat(t), _map(_is, _map(get_tool, _repeat(t, 5)), _repeat(_TOOL_NAME))),
                     _EVENTS5, _CALLBACKS5))
    return _list(_chain(
        _map(_LOST_APPEND, _map(_is_not, _compress(a, _map(_is_not, b, _CALLBACKS5)), _repeat(None))),
        _map(get_tool, (t,))))"""
UNWON_S1 = "    t, get_tool, get_events, set_events = _TOOL[0], _MON[0][0], _MON[0][1], _MON[0][2]\n"
UNWON_GATE = "_map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))"
CONTROLS = {
    # K11: _register counting after its consuming call through _LOST.__iadd__ and an inlined comprehension
    "K11": [(REG_OLD, """    a, b = _tee(_map(register_callback,
                     _compress(_repeat(t), _map(_is, _map(get_tool, _repeat(t, 5)), _repeat(_TOOL_NAME))),
                     _EVENTS5, _CALLBACKS5))
    out = _list(_chain(_map(get_tool, (t,))))
    _LOST.__iadd__([True for x, c in zip(a, _CALLBACKS5) if x is not c])
    return out""")],
    # K12: _unwind_on whose own-anchor gate is read by `in` and a subscript in statement 1
    "K12": [(UNWON_S1, "    t, get_tool, get_events, set_events, mine = _TOOL[0], _MON[0][0], _MON[0][1], _MON[0][2], "
                       "(o.frame in _ANCHORS and _ANCHORS[o.frame] is o)\n")],
    # K12b: _unwind_on's set gated on (o.frame in _ANCHORS,) in the pipeline statement
    "K12b": [(UNWON_GATE + "),\n             _PYU1", "(o.frame in _ANCHORS,)),\n             _PYU1")],
    # K13: _register binding set_events and clearing S when named, its None swallowed by _filter(None, ...)
    "K13": [("    get_tool, register_callback = _MON[0][0], _MON[0][4]\n",
             "    get_tool, register_callback, set_events = _MON[0][0], _MON[0][4], _MON[0][2]\n"),
            ("        _map(get_tool, (t,))))", "        _filter(None, _map(set_events, _compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)), _ZERO1)),\n"
                                             "        _map(get_tool, (t,))))")],
    # K14: _register in revision 7's form, without _tee (two statements)
    # (each previous callback compared with styxx's inside the pipeline and released before its count)
    "K14": [(REG_OLD, """    return _list(_chain(
        _map(_LOST_APPEND, _filter(None, _map(_is_not, _map(register_callback,
                     _compress(_repeat(t), _map(_is, _map(get_tool, _repeat(t, 5)), _repeat(_TOOL_NAME))),
                     _EVENTS5, _CALLBACKS5), _CALLBACKS5))),
        _map(get_tool, (t,))))""")],
}


# Planted blind-shape emissions (positive control #5 in the shapes the text names; the frozen list of eight
# is in mutation_gate_blindspots.json, outside the exam author's read scope: GAP-51)
BLIND_SITE = '''                    "[V5:REENTRANT] a coverage_trace enter or exit was re-entered on the same "'''
BLIND = {
    "split": (BLIND_SITE, '''                    "[V5" + ":REENTRANT] a coverage_trace enter or exit was re-entered on the same "'''),
    "format": (BLIND_SITE, '''                    "[V5{}]".format(":REENTRANT") + " a coverage_trace enter or exit was re-entered on the same "'''),
    "percent": (BLIND_SITE, '''                    "[V5:%s]" % "REENTRANT" + " a coverage_trace enter or exit was re-entered on the same "'''),
    "fstring_code": (BLIND_SITE, '''                    f"[V5:{'REENTRANT'}]" + " a coverage_trace enter or exit was re-entered on the same "'''),
}


def run_blind_controls(path, workdir):
    src = open(path, encoding="utf-8").read()
    out = {}
    for name, (a, b) in BLIND.items():
        if src.count(a) != 1:
            out[name] = {"applied": False}
            continue
        p = os.path.join(workdir, f"blind_{name}_ref_v5f.py")
        open(p, "w").write(src.replace(a, b))
        c = census(Region(p))
        out[name] = {"applied": True, "caught": bool(c["blind"]), "by": [x["shape"] for x in c["blind"]]}
    return out


# Positive control #5 (restated in revision 13, GAP-51): the 8 shapes of mutation_gate_blindspots.json (spec data),
# each planted in a copy of the implementation as a refusal with a fresh code. The control passes for a shape iff
# the census finds the planted literal in a mutable site, the planted copy emits the code, and O13's mutant at
# that site no longer emits it. "Emits": the code is in the planted function's exception, return value, or the
# problem list it appends to.
BLIND8 = {
    "raise via a helper that returns the exception": (
        "def _plant_helper(msg):\n    return GateSpecError(msg)\n\n\n"
        "def _plant():\n    raise _plant_helper(\"[V5:PLANTED_A] a planted refusal\")\n"),
    "raise GateSpecError through a module attribute": (
        "_plant_mod = sys.modules[__name__]\n\n\n"
        "def _plant():\n    raise _plant_mod.GateSpecError(\"[V5:PLANTED_B] a planted refusal\")\n"),
    "raise an alias of GateSpecError": (
        "_PlantE = GateSpecError\n\n\n"
        "def _plant():\n    raise _PlantE(\"[V5:PLANTED_C] a planted refusal\")\n"),
    "recorded problem appended by augmented assignment": (
        "def _plant():\n    global _PLANT_PROBLEMS\n    _PLANT_PROBLEMS += [\"[V5:PLANTED_D] a planted refusal\"]\n"),
    "emission as the value of a return": (
        "def _plant():\n    return \"[V5:PLANTED_E] a planted refusal\"\n"),
    "emission assigned to a name": (
        "def _plant():\n    msg = \"[V5:PLANTED_F] a planted refusal\"\n    raise GateSpecError(msg)\n"),
    "emission inside a conditional expression": (
        "def _plant(x=True):\n    raise GateSpecError(\"[V5:PLANTED_G] a planted refusal\" if x else \"no refusal\")\n"),
    "code in a keyword argument": (
        "class _PlantKwError(Exception):\n    def __init__(self, msg=\"\"):\n        super().__init__(msg)\n\n\n"
        "def _plant():\n    raise _PlantKwError(msg=\"[V5:PLANTED_H] a planted refusal\")\n"),
}


def _plant_emits(path, code):
    m = load(path, f"v5f_plant_{abs(hash(path))}")
    out = []
    try:
        out.append(repr(m._plant()))
    except BaseException as e:                                  # noqa: BLE001
        out.append(f"{type(e).__name__}: {e}")
    out.extend(map(str, m._PLANT_PROBLEMS))
    sys.modules.pop(m.__name__, None)
    return any(f"[V5:{code}]" in x for x in out)


def run_blind8(path, workdir):
    src = open(path, encoding="utf-8").read().rstrip("\n") + "\n\n\n_PLANT_PROBLEMS = []\n\n\n"
    out = {}
    for i, (shape, text) in enumerate(BLIND8.items()):
        code = re.search(r"\[V5:([A-Z_]+)\]", text).group(1)
        p = os.path.join(workdir, f"blind8_{i}_ref_v5f.py")
        open(p, "w").write(src + text)
        R = Region(p)
        sites = [x for x in census(R)["sites"] if x["code"] == code]
        outside = [x for x in census(R)["outside_mutable_site"] if x["code"] == code]
        emits = _plant_emits(p, code)
        after = None
        if sites:
            lines = R.src.split("\n")
            st = sites[0]
            first = lines[st["stmt_line"] - 1]
            indent = first[:len(first) - len(first.lstrip())]
            new = lines[:st["stmt_line"] - 1] + [indent + "pass"] + [""] * (st["stmt_end"] - st["stmt_line"]) + lines[st["stmt_end"]:]
            q = os.path.join(workdir, f"blind8_{i}_o13_ref_v5f.py")
            open(q, "w").write("\n".join(new))
            after = _plant_emits(q, code)
        out[shape] = {"in_mutable_site": bool(sites) and not outside, "emits_planted": emits,
                      "emits_after_o13": after, "caught": bool(sites) and not outside and emits and after is False}
    return out


def run_controls(path, workdir):
    src = open(path, encoding="utf-8").read()
    out = {}
    for name, patches in CONTROLS.items():
        s = src
        applied = True
        for a, b in patches:
            if s.count(a) != 1:
                applied = False
                break
            s = s.replace(a, b)
        if not applied:
            out[name] = {"applied": False}
            continue
        p = os.path.join(workdir, f"{name}_ref_v5f.py")
        open(p, "w").write(s)
        try:
            v = hyg(Region(p))
        except Exception as e:                                # noqa: BLE001
            out[name] = {"applied": True, "rejected": True, "by": [f"load: {type(e).__name__}: {e}"[:120]]}
            continue
        steps = [x for x in v]
        out[name] = {"applied": True, "rejected": bool(steps), "by": sorted({x["clause"] for x in steps})}
    return out


def main(argv):
    def opt(n, d=None):
        return argv[argv.index(n) + 1] if n in argv else d
    impl = os.path.abspath(opt("--impl", os.path.join(HERE, "ref_v5f.py")))
    if opt("--o13-kill"):
        if HERE not in sys.path:
            sys.path.append(HERE)
        import v5f_tmp
        try:
            res = o13_kill(impl, opt("--o13-kill"), opt("--journal"), opt("--deps", os.environ.get("V5F_DEPS_PATH")))
        except v5f_tmp.DiskLow as e:
            return v5f_tmp.stop_disk_low(e, opt("--journal"))
        if opt("--out"):
            json.dump(res, open(opt("--out"), "w"), indent=1)
        print(json.dumps(res, indent=1)[:2000])
        return 0 if res["G_REF_kill"] == "PASS" else 1
    R = Region(impl)
    c = census(R)
    v = hyg(R)
    res = {"impl": impl, "impl_sha256": hashlib.sha256(open(impl, "rb").read()).hexdigest(),
           "python": sys.version.split()[0],
           "G_REF_census": {"coded_literals": len(c["sites"]), "outside_mutable_site": c["outside_mutable_site"],
                            "blind": c["blind"]},
           "G_HYG_violations": v}
    if "--controls" in argv:
        if HERE not in sys.path:
            sys.path.append(HERE)
        import v5f_tmp                                # the control copies are removed when each block exits
        with v5f_tmp.scratch("v5f_hygctl_") as d:
            res["G_HYG_step_controls"] = run_controls(impl, d)
        with v5f_tmp.scratch("v5f_blindctl_") as d:
            res["G_REF_blind_controls"] = run_blind_controls(impl, d)
        with v5f_tmp.scratch("v5f_blind8_") as d:
            res["G_REF_blind8_controls"] = run_blind8(impl, d)
    if opt("--o13-mutants"):
        res["o13_mutants"] = o13_mutants(R, opt("--o13-mutants"))
    ctl_ok = (all(x.get("rejected") for x in res.get("G_HYG_step_controls", {}).values())
              and all(x.get("caught") for x in res.get("G_REF_blind_controls", {}).values())
              and all(x.get("caught") for x in res.get("G_REF_blind8_controls", {}).values()))
    res["G_HYG_verdict"] = "PASS" if not v and ("--controls" not in argv or ctl_ok) else "FAIL"
    # revision 13 (GAP-50): every coded literal of the module must sit in a mutable site (O13 has a compiling
    # mutant for it), and none may be in a blind shape
    res["G_REF_census"]["outside_region"] = sum(1 for x in c["sites"] if x["func"] is None)
    res["G_REF_census_verdict"] = "PASS" if not c["outside_mutable_site"] and not c["blind"] else "FAIL"
    res["verdict"] = res["G_HYG_verdict"]
    if opt("--out"):
        json.dump(res, open(opt("--out"), "w"), indent=1)
    print(json.dumps({"coded_literals": len(c["sites"]), "outside": len(c["outside_mutable_site"]),
                      "blind": len(c["blind"]), "hyg_violations": v[:12], "n_hyg": len(v),
                      "controls": res.get("G_HYG_step_controls"), "blind_controls": res.get("G_REF_blind_controls"), "G_HYG": res["G_HYG_verdict"],
                      "G_REF_census": res["G_REF_census_verdict"]}, indent=1))
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
