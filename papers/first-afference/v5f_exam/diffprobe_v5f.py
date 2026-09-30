"""diffprobe_v5f.py: the differential probe (G_SEM SM2 instrument (d)), its normalizer and its noise mask.

Written by the exam author from the v5f text ("SM2", "Frozen artifacts": corpus_v5f/ and its manifest).

The corpus (corpus_v5f/, built by --build-corpus, hashed in manifest.json):
  exam/<id>.json     every exam case program: the runner's case <id>, run in its frozen placement;
  fuzz/<seed>.json   the fuzzer's program for each frozen seed (fuzz_v5f.py, N = 300);
  crash/<s>.<t>.json the crash sweep's points on ref_v5f.py, per scenario and faulted thread (a record);
  the round 1-4 red-team repros are not in the corpus (SPEC_GAPS.md GAP-55).
manifest.json gives each entry exactly one class, by the frozen rule in classify() (never by judgement):
  envelope: the ids the text lists; every exam case whose program (the case function and the runner
            functions it reaches by name) uses the id-3 fault tool, the id-5 injector or an instruction sweep,
            a signal, PyThreadState_SetAsyncExc or a gc threshold; every crash-sweep point; every fuzzer
            program whose grammar path includes a fault tool;
  equality: every other entry.

The normalizer compares only the spec-fixed observables of the text's closed list:
  refusal codes and exactly the M11 spec-fixed substrings (the leading [V5:CODE]; the NOT_EXERCISED fixed
  sentence; the dispatched/unattributed labels with their dict renderings; the two NESTED_SECTION texts; the
  LAZY_RESULT text and its suffix; the three NO_TRACE wordings; "int too large for a float"; the TRACE_ACTIVE
  texts of M8; the module:qualname that NOT_A_FUNCTION, FOREIGN_DEFINITION, INHERITED, INSTANCE_PATH and
  UNRESOLVED messages name); counts, ends, note codes and problem codes; check_metrics present/usable and each
  note's leading code; _v5_state() fields; fixture __code__ identity; sys.getprofile()/gettrace() identity;
  styxx's tool ownership and the fixtures' local events.
Free-form text, addresses, paths and timings are not compared. The observables of one run are a flat map
path -> value; the calls observed in one run are compared as a multiset (their order across threads is not
an observable of the closed list).

Noise mask: over the manifest's equality entries only, N = 5 unmutated runs per version, each a fresh
process, in the frozen corpus order; a path is masked iff it differs between any two of the runs. If the
mask covers a refusal code, count, end, note code or problem code, the baseline is unclean (G_SEM fails).
The same N = 5 runs are the manifest's freeze-time validation: an equality entry whose runs differ is an
exam-author error, to be reclassified under the rule's own terms before the freeze.

Probe: a mutant is flagged by an equality entry iff an unmasked path differs from the unmutated
implementation's run; by an envelope exam entry iff the case's stated outcome fails (the outcome set or gate
predicate the exam states for it); by an envelope fuzzer program iff its output leaves envelope I6 of the
unmutated run (fuzz_v5f.within_i6). Crash-sweep entries are not probed (SPEC_GAPS.md GAP-57).

Usage:
  python diffprobe_v5f.py --build-corpus                       (writes corpus_v5f/ and its manifest, on 3.12.3)
  python diffprobe_v5f.py --observe ENTRY --impl PATH          (one entry in this process; prints OBS {json})
  python diffprobe_v5f.py --mask --impl PATH [--n 5] [--jobs 3] --out MASK.json
  python diffprobe_v5f.py --probe --impl MUTANT --base PATH --mask MASK.json [--jobs 3] --out RESULT.json
"""
import collections, concurrent.futures as cf, hashlib, inspect, json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ARGV = list(sys.argv)
CORPUS = os.path.join(HERE, "corpus_v5f")
N_MASK = 5


def _opt(n, d=None):
    return ARGV[ARGV.index(n) + 1] if n in ARGV else d


IMPL = os.path.abspath(_opt("--impl", os.path.join(HERE, "ref_v5f.py")))
DEPS = _opt("--deps", os.environ.get("V5F_DEPS_PATH"))

# ---------------------------------------------------------------------------------------------------
# the text's explicit envelope list (manifest rule, first clause)
# ---------------------------------------------------------------------------------------------------
ENVELOPE_IDS = {"X71c", "X92b", "X92c", "X131", "X132", "X133", "X135", "X138", "X139", "X140", "X140f", "X143",
                "X143b", "X143c", "X144", "X145", "X146", "X146b", "X146c", "X146d", "X146e", "X147", "X148",
                "X137d", "X137e", "X138b", "X152", "X153", "X154", "X155", "V65", "V68", "R16"}
ENVELOPE_RE = re.compile(r"^H(10|[1-9])$")                     # the H sweeps
# the rule's second clause, by the program's source: a fault tool, the injector, a signal, SetAsyncExc, a
# finalizer (gc) threshold
FAULT_TOKENS = ("use_tool_id(3", "Injector(", "instruction_sweep(", "_signal", "import signal",
                "SetAsyncExc", "set_threshold")

# ---------------------------------------------------------------------------------------------------
# the normalizer
# ---------------------------------------------------------------------------------------------------
_CODE = re.compile(r"^\[V5:([A-Z_]+)\]")
_BUCKETS = re.compile(r"dispatched (\{.*?\}), unattributed (\{.*?\})")
_NESTED_SAME = re.compile(r"a call there would be on the stack of two openings of section ('.*?'|\".*?\")")
_NESTED_DIFF = re.compile(r"one call would count for both sections ('.*?'|\".*?\") and ('.*?'|\".*?\")")
_NAMED = re.compile(r"[A-Za-z_][\w.]*:[A-Za-z_<][\w.<>]*")
_NAMING_CODES = {"NOT_A_FUNCTION", "FOREIGN_DEFINITION", "INHERITED", "INSTANCE_PATH", "UNRESOLVED"}
FIXED = {
    "not_exercised_sentence": (
        "work on other threads, pools, executors, child processes or asyncio tasks is credited only to a section "
        "that work opens itself; generator and coroutine objects created before the trace are never credited; a "
        "call counts only when it returns, yields or raises from inside its body while the tracer is active"),
    "lazy": "whatever of its body runs after the section closed does not count",
    "lazy_suffix": "(its body had not started)",
    "overflow": "int too large for a float",
    "no_trace_1": "declares 'exercises' but the result is a",
    "no_trace_2": "declares 'exercises' but the result has no",
    "no_trace_3": "not an exact dict (e.g. loaded with object_pairs_hook)",
    "trace_active_never": "the tracer was never entered",
    "trace_active_active": "the tracer is active",
}


def norm_text(msg):
    """A refusal or note text -> its spec-fixed observables only."""
    msg = msg if type(msg) is str else str(msg)
    m = _CODE.match(msg)
    out = {"code": m.group(1) if m else None}
    for k, s in FIXED.items():
        if s in msg:
            out[k] = True
    b = _BUCKETS.search(msg)
    if b:
        out["buckets"] = [b.group(1), b.group(2)]
    for k, rx in (("nested_same", _NESTED_SAME), ("nested_diff", _NESTED_DIFF)):
        n = rx.search(msg)
        if n:
            out[k] = list(n.groups())
    if out["code"] in _NAMING_CODES:
        out["names"] = sorted(set(_NAMED.findall(msg)))
    return out


def norm_record(rec):
    if type(rec) is not dict:
        return {"type": type(rec).__name__}
    secs = {}
    for s, ops in (rec.get("sections") or {}).items():
        secs[str(s)] = [{"calls": dict(o.get("calls", {})), "ambiguous": dict(o.get("ambiguous", {})),
                         "end": o.get("end"), "notes": [norm_text(n)["code"] for n in o.get("notes", [])]}
                        for o in ops]
    return {"sections": secs, "uncredited": rec.get("uncredited"),
            "problems": [norm_text(p)["code"] for p in rec.get("problems", [])]}


def norm_verdict(v):
    return {"verdict": getattr(v, "verdict", None), "gates": dict(getattr(v, "gates", {}) or {}),
            "coverage": getattr(v, "coverage", None)}


def norm_metrics(d):
    if type(d) is not dict:
        return {"type": type(d).__name__}
    out = {}
    for k, v in d.items():
        if type(v) is dict:
            note = v.get("note")
            out[str(k)] = {"present": v.get("present"), "usable": v.get("usable"),
                           "note": norm_text(note)["code"] if type(note) is str else note}
    return out


def norm_exc(e):
    return {"raised": type(e).__name__, **norm_text(str(e))}


def norm_child(x):
    """A spawned child's JSON (a subprocess case): its codes, counts and flags, never its free text."""
    if isinstance(x, dict):
        return {str(k): norm_child(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [norm_child(v) for v in x]
    if isinstance(x, str):
        if x.startswith("[V5:"):
            return norm_text(x)
        return x if re.fullmatch(r"[A-Za-z0-9_:.\- ]{0,80}", x) and "/" not in x else "<text>"
    return x


def flatten(x, pre="", out=None):
    out = {} if out is None else out
    if isinstance(x, dict):
        for k in sorted(x, key=str):
            flatten(x[k], f"{pre}/{k}", out)
    elif isinstance(x, list):
        for i, v in enumerate(x):
            flatten(v, f"{pre}[{i}]", out)
        if not x:
            out[pre] = []
    else:
        out[pre] = x
    return out


SPEC_FIXED_KEYS = re.compile(r"(/code$|/calls/|/ambiguous/|/end$|/notes\[|/problems\[|/raised$|/verdict$)")

# ---------------------------------------------------------------------------------------------------
# observing one entry, in this process
# ---------------------------------------------------------------------------------------------------
def load_runner(impl):
    sys.argv = [os.path.join(HERE, "run_protocol_v5f_exam.py"), "--impl", impl] + (["--deps-path", DEPS] if DEPS else [])
    sys.path.insert(0, HERE)
    import importlib
    return importlib.import_module("run_protocol_v5f_exam")


def observe_exam(cid, impl):
    R = load_runner(impl)
    P = R.P
    calls = []
    live = {"on": False, "skip": None}

    def wrap(owner, name, kind):
        orig = owner.__dict__[name]

        def w(*a, **k):
            if not live["on"] or (a and a[0] is live["skip"]):
                return orig(*a, **k)
            try:
                r = orig(*a, **k)
            except BaseException as e:                      # noqa: BLE001
                calls.append([kind, norm_exc(e)])
                raise
            if kind == "record":
                calls.append([kind, norm_record(r)])
            elif kind == "score":
                calls.append([kind, norm_verdict(r)])
            elif kind == "check_metrics":
                calls.append([kind, norm_metrics(r)])
            else:
                calls.append([kind, "ok"])
            return r
        w.__wrapped_orig__ = orig
        setattr(owner, name, w)

    fac = P._CoverageTracer
    for n in ("__enter__", "__exit__", "run", "record"):
        wrap(fac, n, n)
    wrap(P.Experiment, "score", "score")
    wrap(P.Experiment, "check_metrics", "check_metrics")
    wrap(P.Experiment, "__init__", "Experiment")
    orig_ct = P.coverage_trace

    def ct(exp):
        if not live["on"]:
            return orig_ct(exp)
        try:
            return orig_ct(exp)
        except BaseException as e:                          # noqa: BLE001
            calls.append(["coverage_trace", norm_exc(e)])
            raise
    P.coverage_trace = ct
    children = []
    for n in ("run_sub", "run_sub_patched", "run_child"):
        if hasattr(R, n):
            o = getattr(R, n)

            def cw(*a, _o=o, **k):
                r = _o(*a, **k)
                children.append(norm_child(r))
                return r
            setattr(R, n, cw)
    prof0 = (sys.getprofile(), sys.gettrace())
    fn = R.BY_ID[cid][2]
    pl = R.placement(cid)
    live["on"] = True
    if pl == "self-trace":
        spec = R.gates({"G0": R.SELF_TARGETS})
        path = os.path.join(R.REPO, "PREREG_SELF.md")
        with open(path, "w") as fh:
            fh.write(f"# the exam's self-trace prereg\n\n```gates\n{json.dumps(spec, indent=1)}\n```\n")
        subprocess.run(R._git + ["add", "."], cwd=R.REPO, check=True)
        subprocess.run(R._git + ["commit", "-q", "-m", "self-trace prereg"], cwd=R.REPO, check=True)
        live["on"] = False
        sexp = P.Experiment(path)
        selfcov = P.coverage_trace(sexp)
        live["skip"] = selfcov
        selfcov.__enter__()
        live["on"] = True
        ok, detail, left = R.run_in_self(cid, selfcov, "G0")
        live["on"] = False
        selfcov.__exit__(None, None, None)
    else:
        ok, detail, left = R.run_main(cid) if (pl == "main" or cid in R.CHILD) else (*R._call(fn), [])
    live["on"] = False
    st = dict(P._v5_state())
    st.pop("pid", None)
    t = st.get("tool")
    mon = sys.monitoring
    codes, local = {}, {}
    for k, (f, code) in R.ORIG.items():
        codes["/".join(k)] = "original" if f.__code__ is code else ("equal" if f.__code__ == code else "other")
        if t is not None and mon.get_tool(t) is not None:
            local["/".join(k)] = mon.get_local_events(t, f.__code__)
    tools = {}
    for i in range(6):
        nm = mon.get_tool(i)
        tools[str(i)] = None if nm is None else ("styxx" if nm is P._TOOL_NAME else "other")
    return {"entry": f"exam/{cid}", "placement": pl, "exam_ok": bool(ok),
            "calls": sorted(calls, key=lambda c: json.dumps(c, sort_keys=True, default=str)),
            "children": children,
            "end": {"state": st, "fixture_code": codes, "fixture_local_events": local,
                    "profile_same": sys.getprofile() is prof0[0], "trace_same": sys.gettrace() is prof0[1],
                    "tools": tools}}


def observe(entry, impl):
    kind, _, name = entry.partition("/")
    if kind == "exam":
        return observe_exam(json.load(open(os.path.join(CORPUS, entry)))["case"], impl)
    if kind == "fuzz":
        seed = json.load(open(os.path.join(CORPUS, entry)))["seed"]
        sys.argv = [os.path.join(HERE, "fuzz_v5f.py")]
        import runpy
        fz = runpy.run_path(os.path.join(HERE, "fuzz_v5f.py"), run_name="fuzz")
        return {"entry": entry, "fuzz": fz["run_program"](seed, impl)}
    return {"entry": entry, "not_probed": "GAP-57"}


def run_entry(py, entry, impl, timeout=900):
    env = dict(os.environ)
    if DEPS:
        env["V5F_DEPS_PATH"] = DEPS
    try:
        r = subprocess.run([py, os.path.abspath(__file__), "--observe", entry, "--impl", impl],
                           capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return {"entry": entry, "crash": "TIMEOUT"}
    lines = [x for x in r.stdout.splitlines() if x.startswith("OBS ")]
    if not lines:
        return {"entry": entry, "crash": (r.stderr.strip().splitlines() or ["?"])[-1][:200]}
    return json.loads(lines[-1][4:])


def comparable(obs):
    """The flat map the mask and the probe compare: everything but the exam's own pass/fail and placement."""
    o = {k: v for k, v in obs.items() if k not in ("exam_ok", "placement", "entry")}
    if "fuzz" in o:
        o["fuzz"] = norm_child(o["fuzz"])
    return flatten(o)

# ---------------------------------------------------------------------------------------------------
# the corpus and its manifest
# ---------------------------------------------------------------------------------------------------
def _reach(R, fn, seen):
    """The runner functions a case function reaches by name (its code objects' co_names, recursively)."""
    out = []
    stack = [fn.__code__]
    while stack:
        c = stack.pop()
        for n in c.co_names:
            g = vars(R).get(n)
            if inspect.isfunction(g) and g.__module__ == R.__name__ and n not in seen:
                seen.add(n)
                out.append(g)
                stack.append(g.__code__)
        stack.extend(k for k in c.co_consts if inspect.iscode(k))
    return out


def classify_exam(R, cid, fn):
    if cid in ENVELOPE_IDS:
        return "envelope", "listed by the text"
    if ENVELOPE_RE.match(cid):
        return "envelope", "an H sweep"
    srcs = [fn] + _reach(R, fn, set())
    for f in srcs:
        try:
            src = inspect.getsource(f)
        except (OSError, TypeError):
            continue
        for t in FAULT_TOKENS:
            if t in src:
                return "envelope", f"source token {t!r} in {f.__name__}"
    return "equality", "no clause applies"


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def build_corpus(py312):
    R = load_runner(os.path.join(HERE, "ref_v5f.py"))
    import runpy
    fz = runpy.run_path(os.path.join(HERE, "fuzz_v5f.py"), run_name="fuzz")
    os.makedirs(os.path.join(CORPUS, "exam"), exist_ok=True)
    os.makedirs(os.path.join(CORPUS, "fuzz"), exist_ok=True)
    os.makedirs(os.path.join(CORPUS, "crash"), exist_ok=True)
    man = {"rule": "diffprobe_v5f.py classify_exam / fuzz fault / crash point (the manifest rule of the text)",
           "runner_sha256": _sha(os.path.join(HERE, "run_protocol_v5f_exam.py")),
           "not_in_corpus": {"round 1-4 red-team repros": "GAP-55"}, "entries": {}}
    for cid, fam, row, fn in R.CASES:
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", cid)
        p = f"exam/{safe}.json"
        json.dump({"kind": "exam", "case": cid, "row": row, "placement": R.placement(cid)},
                  open(os.path.join(CORPUS, p), "w"), indent=1)
        cls, why = classify_exam(R, cid, fn)
        man["entries"][p] = {"class": cls, "why": why}
    for seed in range(fz["N_FROZEN"]):
        prog = fz["generate"](seed)
        p = f"fuzz/{seed:03d}.json"
        json.dump({"kind": "fuzz", "seed": seed, "program": prog}, open(os.path.join(CORPUS, p), "w"), indent=1)
        man["entries"][p] = ({"class": "envelope", "why": "grammar path includes a fault tool"} if prog["fault"]
                             else {"class": "equality", "why": "no fault tool"})
    out = os.path.join(CORPUS, "crash", "_points_3.12.3.json")
    subprocess.run([py312, os.path.join(HERE, "crash_sweep_v5f.py"), "--discover-only", "--out", out],
                   capture_output=True, text=True, timeout=3600, check=True)
    d = json.load(open(out))
    os.remove(out)
    for sc, roles in d["scenarios"].items():
        for role, v in roles.items():
            if not isinstance(v, dict) or "point_list" not in v:
                continue
            p = f"crash/{sc}.{role}.json"
            json.dump({"kind": "crash", "scenario": sc, "faulted": role, "python": d["python"],
                       "impl": "ref_v5f.py", "points": v["point_list"]}, open(os.path.join(CORPUS, p), "w"), indent=1)
            man["entries"][p] = {"class": "envelope", "why": "a crash-sweep point set"}
    for p in man["entries"]:
        man["entries"][p]["sha256"] = _sha(os.path.join(CORPUS, p))
    json.dump(man, open(os.path.join(CORPUS, "manifest.json"), "w"), indent=1, sort_keys=True)
    n = collections.Counter(v["class"] for v in man["entries"].values())
    print(f"corpus: {len(man['entries'])} entries, {dict(n)}")
    return 0

# ---------------------------------------------------------------------------------------------------
# the noise mask (and the manifest's freeze-time validation) and the probe
# ---------------------------------------------------------------------------------------------------
def manifest():
    return json.load(open(os.path.join(CORPUS, "manifest.json")))


def mask(py, impl, n, jobs, only=None):
    man = manifest()
    eq = [p for p, v in sorted(man["entries"].items()) if v["class"] == "equality"]
    if only:
        eq = [p for p in eq if p in only]
    runs = {p: [] for p in eq}
    with cf.ThreadPoolExecutor(jobs) as ex:
        for i in range(n):
            for p, o in zip(eq, ex.map(lambda p: run_entry(py, p, impl), eq)):
                runs[p].append(o)
    masked, unstable, crashes = {}, {}, {}
    for p, rs in runs.items():
        if any("crash" in r for r in rs):
            crashes[p] = [r.get("crash") for r in rs if "crash" in r]
            continue
        flats = [comparable(r) for r in rs]
        keys = set().union(*flats)
        m = sorted(k for k in keys if len({json.dumps(f.get(k, "<absent>"), sort_keys=True, default=str) for f in flats}) > 1)
        if m:
            masked[p] = m
            bad = [k for k in m if SPEC_FIXED_KEYS.search(k)]
            if bad:
                unstable[p] = bad
    return {"impl": impl, "python": sys.version.split()[0], "n": n, "entries": len(eq),
            "masked": masked, "unclean": unstable, "crashes": crashes,
            "baseline": "CLEAN" if not unstable and not crashes else "UNCLEAN"}


def probe(py, mut, base, mk, jobs):
    man = manifest()
    masked = mk.get("masked", {})
    flagged = {}
    entries = sorted(man["entries"].items())

    def one(item):
        p, v = item
        if p.startswith("crash/"):
            return p, None
        a = run_entry(py, p, mut)
        if v["class"] == "equality":
            b = run_entry(py, p, base)
            if "crash" in a:
                return p, f"crash: {a['crash']}"
            fa, fb = comparable(a), comparable(b)
            diff = [k for k in set(fa) | set(fb) if k not in masked.get(p, ()) and fa.get(k) != fb.get(k)]
            return p, (sorted(diff)[:10] or None)
        if p.startswith("exam/"):
            return p, None if a.get("exam_ok") else "the case's stated outcome fails"
        b = run_entry(py, p, base)
        import runpy
        fz = runpy.run_path(os.path.join(HERE, "fuzz_v5f.py"), run_name="fuzz")
        if "crash" in a:
            return p, f"crash: {a['crash']}"
        return p, None if fz["within_i6"](a["fuzz"], b["fuzz"]) else "outside envelope I6"
    with cf.ThreadPoolExecutor(jobs) as ex:
        for p, r in ex.map(one, entries):
            if r:
                flagged[p] = r
    return {"mutant": mut, "base": base, "python": sys.version.split()[0], "flagged": flagged,
            "detected": bool(flagged), "not_probed": [p for p, _ in entries if p.startswith("crash/")]}


def main():
    if "--observe" in ARGV:
        print("OBS " + json.dumps(observe(_opt("--observe"), IMPL), default=str, sort_keys=True))
        sys.stdout.flush()
        os._exit(0)
    if "--build-corpus" in ARGV:
        return build_corpus(sys.executable)
    jobs = int(_opt("--jobs", "3"))
    if "--mask" in ARGV:
        only = set(_opt("--only").split(",")) if _opt("--only") else None
        t0 = time.monotonic()
        r = mask(sys.executable, IMPL, int(_opt("--n", str(N_MASK))), jobs, only)
        r["seconds"] = round(time.monotonic() - t0, 1)
        json.dump(r, open(_opt("--out"), "w"), indent=1, sort_keys=True)
        print(json.dumps({k: r[k] for k in ("entries", "baseline")}), len(r["masked"]), "entries with a mask;",
              len(r["unclean"]), "unclean")
        return 0 if r["baseline"] == "CLEAN" else 1
    if "--probe" in ARGV:
        r = probe(sys.executable, IMPL, os.path.abspath(_opt("--base")), json.load(open(_opt("--mask"))), jobs)
        json.dump(r, open(_opt("--out"), "w"), indent=1)
        print(json.dumps({"detected": r["detected"], "flagged": len(r["flagged"])}))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
