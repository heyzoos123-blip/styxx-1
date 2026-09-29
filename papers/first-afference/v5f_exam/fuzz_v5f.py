"""fuzz_v5f.py: the oracle fuzzer (G_SEM instrument (c); G_COVER pass 3), written by the exam author.

Its grammar covers what the text lists: nested tracers, shared and cross-named sections, clones, swaps,
generator throw()/close(), cross-thread coroutine sections, gc.freeze, raising targets and lower-id fault
tools. Each program is generated from a frozen seed and run in a fresh process of the same interpreter,
once on the implementation under test and once on the oracle, ref_v5f.py. The spec-fixed observables of the
two runs are compared (the normalizer's closed list: codes, counts, ends, note and problem codes, the
NOT_EXERCISED buckets, exceptions' codes, _v5_state() fields, fixture __code__ identity). A program whose
grammar path includes a fault tool is an `envelope` program: its output is checked against envelope I6 of
the oracle's run instead of for equality.

Frozen: SEEDS = range(0, N) with N = 300; each program at most 8 statements.

Usage: python fuzz_v5f.py [--impl PATH] [--n 300] [--out RESULT.json]
       python fuzz_v5f.py --program SEED --impl PATH      (one program, in this process; prints its observables)
"""
import json, os, random, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ARGV = list(sys.argv)
N_FROZEN = 300
MAX_STMTS = 8


def _opt(n, d=None):
    return ARGV[ARGV.index(n) + 1] if n in ARGV else d


IMPL = os.path.abspath(_opt("--impl", os.path.join(HERE, "ref_v5f.py")))
ORACLE = os.path.join(HERE, "ref_v5f.py")

FIXTURE = '''
import asyncio
CALLS = []
def a(x=0): return x + 1
def b(x=0): return x + 2
def c(x=0): return x + 3
def u(x=0): return -1
def r():
    raise ValueError("r raises")
def gen():
    yield a()
    yield b()
async def co():
    a()
    await Once()
    b()
class Once:
    def __await__(self):
        yield
'''

TARGETS = ["fz:a", "fz:b", "fz:c", "fz:gen", "fz:r"]


# ---------------------------------------------------------------------------------------------------
# the grammar
# ---------------------------------------------------------------------------------------------------
def generate(seed):
    rng = random.Random(seed)
    ntr = rng.choice([1, 1, 2, 2, 3])
    gates = []
    for i in range(ntr):
        k = rng.choice([1, 2])
        gs = {}
        for g in range(k):
            name = rng.choice(["A", "B", "C"])
            if name in gs:
                continue
            decl = sorted(rng.sample(TARGETS, rng.choice([1, 2])))
            sec = rng.choice([name, name, "S", "A" if name != "A" else "B"])     # shared / cross-named
            gs[name] = {"exercises": decl, "section": sec}
        gates.append(gs)
    body_ops = ["call_a", "call_b", "call_c", "call_r", "gen_iter", "gen_throw", "gen_close", "clone_same",
                "clone_foreign", "clone_keep", "swap_restore", "swap_keep", "freeze", "nested", "hop"]
    prog = {"seed": seed, "gates": gates, "stmts": [], "fault": None}
    for _ in range(rng.randint(2, MAX_STMTS)):
        t = rng.randrange(ntr)
        kind = rng.choice(["section", "section", "section", "async_section", "outside"])
        ops = [rng.choice(body_ops) for _ in range(rng.randint(1, 4))]
        sec = rng.choice(sorted({g["section"] for g in gates[t].values()} | {"A"}))
        prog["stmts"].append({"tracer": t, "kind": kind, "section": sec, "ops": ops})
    if rng.random() < 0.25:
        prog["fault"] = {"tool": rng.choice([3, 2]), "event": rng.choice(["PY_START", "PY_RETURN"]),
                         "nth": rng.randint(1, 6)}
    return prog


# ---------------------------------------------------------------------------------------------------
# one program, in this process
# ---------------------------------------------------------------------------------------------------
def run_program(seed, impl):
    import asyncio, gc, importlib, importlib.util, re, subprocess as sp, tempfile, textwrap, threading, types
    work = tempfile.mkdtemp(prefix="v5f_fuzz_")
    fixdir, repo = os.path.join(work, "fx"), os.path.join(work, "repo")
    os.makedirs(fixdir); os.makedirs(repo)
    open(os.path.join(fixdir, "fz.py"), "w").write(textwrap.dedent(FIXTURE))
    sys.path.insert(0, fixdir)
    fz = importlib.import_module("fz")
    spec = importlib.util.spec_from_file_location("v5f_impl_fuzz", impl)
    P = importlib.util.module_from_spec(spec)
    sys.modules["v5f_impl_fuzz"] = P
    spec.loader.exec_module(P)
    prog = generate(seed)
    exps = []
    for i, gs in enumerate(prog["gates"]):
        spec_ = {"gates": {n: {"metric": "m", "op": ">=", "value": 0.0, **g} for n, g in gs.items()},
                 "outcomes": [{"when": {n: True for n in gs}, "verdict": "PASS"}], "smoke_verdict": "INVALID__smoke"}
        path = os.path.join(repo, f"PREREG_{i}.md")
        open(path, "w").write("# fuzz\n\n```gates\n" + json.dumps(spec_) + "\n```\n")
    git = ["git", "-c", "user.name=fuzz", "-c", "user.email=fuzz@invalid", "-c", "commit.gpgsign=false"]
    sp.run(["git", "init", "-q"], cwd=repo, check=True)
    sp.run(git + ["add", "."], cwd=repo, check=True)
    sp.run(git + ["commit", "-q", "-m", "fuzz"], cwd=repo, check=True)
    code_re = re.compile(r"\[V5:([A-Z_]+)\]")

    def code(e):
        m = code_re.match(str(e))
        return m.group(1) if m else type(e).__name__

    orig = {n: getattr(fz, n).__code__ for n in ("a", "b", "c", "u", "r", "gen")}
    obs = {"seed": seed, "events": []}
    fault_state = {"n": 0}
    if prog["fault"]:
        f = prog["fault"]
        mon = sys.monitoring
        mon.use_tool_id(f["tool"], "fuzz-fault")
        ev = getattr(mon.events, f["event"])
        def cb(*args):
            fault_state["n"] += 1
            if fault_state["n"] == f["nth"]:
                raise RuntimeError("fuzz fault tool")
        mon.register_callback(f["tool"], ev, cb)
        mon.set_events(f["tool"], ev)
    tracers = []
    keep = []
    for i in range(len(prog["gates"])):
        try:
            exp = P.Experiment(os.path.join(repo, f"PREREG_{i}.md"))
            cov = P.coverage_trace(exp)
            cov.__enter__()
            tracers.append((exp, cov))
            obs["events"].append(["enter", i, "ok"])
        except Exception as e:                        # noqa: BLE001
            tracers.append((None, None))
            obs["events"].append(["enter", i, code(e)])

    def body(ops, t):
        out = []
        for op in ops:
            try:
                if op == "call_a": fz.a()
                elif op == "call_b": fz.b()
                elif op == "call_c": fz.c()
                elif op == "call_r":
                    try:
                        fz.r()
                    except ValueError:
                        pass
                elif op == "gen_iter": list(fz.gen())
                elif op == "gen_throw":
                    g = fz.gen(); next(g)
                    try:
                        g.throw(KeyError("fuzz"))
                    except KeyError:
                        pass
                elif op == "gen_close":
                    g = fz.gen(); next(g); g.close()
                elif op == "clone_same": types.FunctionType(fz.a.__code__, fz.a.__globals__)(0)
                elif op == "clone_foreign": types.FunctionType(fz.a.__code__, {})(0)
                elif op == "clone_keep": keep.append(types.FunctionType(fz.b.__code__, fz.b.__globals__))
                elif op == "swap_restore":
                    c0 = fz.c.__code__; fz.c.__code__ = fz.u.__code__; fz.c(); fz.c.__code__ = c0
                elif op == "swap_keep":
                    fz.c.__code__ = fz.u.__code__
                elif op == "freeze":
                    gc.freeze(); fz.a(); gc.unfreeze(); gc.collect()
                elif op == "nested":
                    j = (t + 1) % len(tracers)
                    exp2, cov2 = tracers[j]
                    if cov2 is not None:
                        sec2 = next(iter(exp2.coverage.values()))["section"]
                        cov2.run(sec2, fz.b)
                elif op == "hop":
                    exp_, cov_ = tracers[t]
                    sec_ = next(iter(exp_.coverage.values()))["section"]
                    co = cov_.run_async(sec_, fz.co)
                    th = threading.Thread(target=co.send, args=(None,)); th.start(); th.join(10)
                    try:
                        co.send(None)
                    except StopIteration:
                        pass
                out.append([op, "ok"])
            except Exception as e:                    # noqa: BLE001
                out.append([op, code(e)])
        return out

    for st in prog["stmts"]:
        exp, cov = tracers[st["tracer"]]
        if cov is None:
            continue
        try:
            if st["kind"] == "outside":
                r = body(st["ops"], st["tracer"])
            elif st["kind"] == "async_section":
                async def _wrap(ops, t):
                    return body(ops, t)
                r = asyncio.run(cov.run_async(st["section"], _wrap, st["ops"], st["tracer"]))
            else:
                r = cov.run(st["section"], body, st["ops"], st["tracer"])
            obs["events"].append([st["kind"], st["section"], r])
        except Exception as e:                        # noqa: BLE001
            obs["events"].append([st["kind"], st["section"], code(e)])
    for i, (exp, cov) in enumerate(tracers):
        if cov is None:
            continue
        try:
            cov.__exit__(None, None, None)
            obs["events"].append(["exit", i, "ok"])
        except Exception as e:                        # noqa: BLE001
            obs["events"].append(["exit", i, code(e)])
    if prog["fault"]:
        f = prog["fault"]
        sys.monitoring.set_events(f["tool"], 0)
        sys.monitoring.register_callback(f["tool"], getattr(sys.monitoring.events, f["event"]), None)
        sys.monitoring.free_tool_id(f["tool"])
    obs["tracers"] = []
    for i, (exp, cov) in enumerate(tracers):
        if cov is None:
            obs["tracers"].append(None)
            continue
        try:
            rec = cov.record()
        except Exception as e:                        # noqa: BLE001
            obs["tracers"].append({"record": code(e)})
            continue
        try:
            v = exp.score({"m": 1.0, "coverage_trace": rec})
            score = ["PASS", v.coverage]
        except Exception as e:                        # noqa: BLE001
            score = ["REFUSE", code(e)]
        obs["tracers"].append({
            "score": score,
            "sections": {s: [{"calls": o["calls"], "ambiguous": o["ambiguous"], "end": o["end"],
                              "notes": [code(n) for n in o["notes"]]} for o in ops] for s, ops in rec["sections"].items()},
            "problems": [code(p) for p in rec["problems"]], "uncredited": rec["uncredited"]})
    keep.clear()
    gc.collect()
    st = P._v5_state()
    obs["state"] = {k: st[k] for k in ("anchors", "global_events", "guard", "cut_current", "tool_ours")}
    obs["state"]["mints"] = sorted((m["target"], m["holders"], m["installed"]) for m in st["mints"])
    obs["fixtures_restored"] = {n: getattr(fz, n).__code__ is orig[n] for n in orig}
    obs["fault"] = prog["fault"]
    return obs


def run_sub(seed, impl, py=None):
    r = subprocess.run([py or sys.executable, os.path.abspath(__file__), "--program", str(seed), "--impl", impl],
                       capture_output=True, text=True, timeout=120)
    lines = [x for x in r.stdout.splitlines() if x.startswith("FUZZ ")]
    if not lines:
        return {"crash": (r.stderr.strip().splitlines() or ["?"])[-1][:200]}
    return json.loads(lines[-1][5:])


def within_i6(got, want):
    """An envelope program: each tracer's counts at most the oracle's, ends and codes within its envelope."""
    for g, w in zip(got.get("tracers", []), want.get("tracers", [])):
        if g is None or w is None or "sections" not in g or "sections" not in w:
            continue
        for s, ops in g["sections"].items():
            wops = w["sections"].get(s, [])
            wc = {}
            for o in wops:
                for k, v in o["calls"].items():
                    wc[k] = wc.get(k, 0) + v
            gc_ = {}
            for o in ops:
                for k, v in o["calls"].items():
                    gc_[k] = gc_.get(k, 0) + v
            if any(v > wc.get(k, 0) for k, v in gc_.items()):
                return False
    return True


def main():
    if "--program" in ARGV:
        print("FUZZ " + json.dumps(run_program(int(_opt("--program")), IMPL), default=str, sort_keys=True))
        return 0
    n = int(_opt("--n", str(N_FROZEN)))
    t0 = time.monotonic()
    diffs, envelope_bad, crashes = [], [], []
    for seed in range(n):
        want = run_sub(seed, ORACLE)
        got = want if IMPL == ORACLE and "--twice" not in ARGV else run_sub(seed, IMPL)
        if "crash" in got or "crash" in want:
            crashes.append((seed, got.get("crash"), want.get("crash")))
            continue
        if got == want:
            continue
        if want.get("fault"):
            if not within_i6(got, want):
                envelope_bad.append(seed)
        else:
            diffs.append(seed)
    res = {"impl": IMPL, "python": sys.version.split()[0], "n": n, "equality_diffs": diffs,
           "envelope_violations": envelope_bad, "crashes": crashes, "seconds": round(time.monotonic() - t0, 1)}
    res["verdict"] = "PASS" if not diffs and not envelope_bad and not crashes else "FAIL"
    if _opt("--out"):
        json.dump(res, open(_opt("--out"), "w"), indent=1)
    print(json.dumps(res)[:800])
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
