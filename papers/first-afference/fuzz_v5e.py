"""Oracle fuzzer for protocol v5e -- frozen with PREREG v5e, before the implementation exists.

Hand-written cases test the shapes someone thought of. This tests the attribution RULE: a seeded
generator builds random harness programs, and because the generator places every call itself it
knows, by construction, which section's stack each call lands on. The tracer's record must equal
that oracle exactly, program after program.

THE ORACLE (from the frozen spec: "a counted frame is credited to opening O iff O's anchor ... is
met on the frame's f_back chain before the first Handle._run frame"):

* a call is credited to the nearest section opened on its own stack segment;
* a stack segment ENDS at a thread, a thread-pool job, a parallel thread group, a generator
  consumed on another thread, an asyncio task, a gather child, asyncio.to_thread, or an event
  loop run inside the segment (everything a loop runs passes through its dispatch frame) -- the
  body on the far side starts with no section;
* a segment CONTINUES through a direct await, recursion, a generator consumed inline, a
  functools.partial, an alias, and an exception raised and caught (a section whose function
  raises keeps its counts; its end is "raised");
* decoys never count: a factory sibling of a declared product, a functools.wraps sibling, a
  clone of a declared function's code made before the trace, and the wrapped inner body called
  directly. Each shares code with a declared target, which is exactly what minting must see
  through.

POSITIVE CONTROLS (pre-freeze, committed as ``protocol_v5e_fuzz_controls.json``): the first
version of this fuzzer was blind to the dispatch cut -- every loop it generated ran at the top,
so no anchor ever sat below one. The ``loop`` node exists because a control caught that.

The generator never opens a section inside a section on one segment (that is NESTED_SECTION, a
refusal the exam covers); every program therefore records problems == [] and all ambiguous
counters empty, and both are checked. Programs are interpreted, not generated as source, so the
interpreter's own frames sit between a section's anchor and its calls, deepening every walk.

Writes ``protocol_v5e_fuzz.json`` (or ``$STYXX_V5_RESULT_OUT``). Honours
``STYXX_V5_IMPORT_ROOT`` like the exam. Read-only on the repo otherwise.
"""
from __future__ import annotations

import argparse
import asyncio
import functools
import hashlib
import json
import os
import random
import subprocess
import sys
import tempfile
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
if os.environ.get("STYXX_V5_IMPORT_ROOT"):
    sys.path.insert(0, os.environ["STYXX_V5_IMPORT_ROOT"])
else:
    sys.path.insert(0, str(ROOT))

FX = "_v5e_fz"
FIXTURE = '''
import functools
import types


def t0(x=0): return x
def t1(x=0): return x + 1
def t2(x=0): return x + 2


def _mk(k):
    def prod(x=0): return x + k
    return prod


p_real = _mk(10)          # declared: a factory product
p_decoy = _mk(20)         # decoy: same code object as p_real's, before minting


def _inner(x=0): return x * 2


@functools.wraps(_inner)
def w_real(x=0): return _inner(x)       # declared: a wraps wrapper is its own target


@functools.wraps(_inner)
def w_decoy(x=0): return _inner(x)      # decoy: wraps sibling of the same inner


t0_preclone = types.FunctionType(t0.__code__, globals(), "t0_preclone", t0.__defaults__)


def gen_t1(n):
    for i in range(n):
        t1(i)
        yield i
'''
TARGETS = ["t0", "t1", "t2", "p_real", "w_real"]
DECOYS = ["p_decoy", "w_decoy", "t0_preclone", "_inner"]
SECTIONS = ["S0", "S1", "S2", "S3"]


class _Boom(Exception):
    pass


# -- generation ---------------------------------------------------------------------------------

def gen_sync(rng: random.Random, depth: int, in_sec: bool, budget: list,
             loop_running: bool = False) -> list:
    """A list of sync nodes. in_sec: a section is open on this segment (no new one may open).
    loop_running: this code runs on a thread whose event loop is running, so it may not start
    another one (asyncio.run would raise)."""
    out = []
    for _ in range(rng.randint(1, 4)):
        if budget[0] <= 0:
            break
        budget[0] -= 1
        r = rng.random()
        leaf = depth <= 0
        if r < 0.28 or (leaf and r < 0.6):
            out.append(("call", rng.choice(TARGETS)))
        elif r < 0.38 or leaf:
            kind = rng.choice(["decoy", "partial", "alias", "gen"])
            if kind == "decoy":
                out.append(("decoy", rng.choice(DECOYS)))
            elif kind == "gen":
                out.append(("gen", rng.randint(0, 3)))
            else:
                out.append((kind, rng.choice(TARGETS)))
        elif r < 0.55 and not in_sec:
            out.append(("sec", rng.choice(SECTIONS),
                        gen_sync(rng, depth - 1, True, budget, loop_running)))
        elif r < 0.60 and not in_sec:
            out.append(("secraise", rng.choice(SECTIONS),
                        gen_sync(rng, depth - 1, True, budget, loop_running)))
        elif r < 0.68:
            out.append(("thread", gen_sync(rng, depth - 1, False, budget)))
        elif r < 0.74:
            out.append(("par", [gen_sync(rng, depth - 1, False, budget)
                                for _ in range(rng.randint(2, 3))]))
        elif r < 0.80:
            out.append(("pool", [gen_sync(rng, depth - 1, False, budget)
                                 for _ in range(rng.randint(1, 3))]))
        elif r < 0.84:
            out.append(("deep", rng.randint(1, 40),
                        gen_sync(rng, depth - 1, in_sec, budget, loop_running)))
        elif r < 0.89:
            out.append(("exc", gen_sync(rng, depth - 1, in_sec, budget, loop_running)))
        elif r < 0.95 and not loop_running:
            # an event loop run INSIDE this segment: everything in it is past the dispatch cut
            out.append(("loop", gen_async(rng, depth - 1, False, budget)))
        else:
            out.append(("genthread", rng.randint(0, 3)))
    return out


def gen_async(rng: random.Random, depth: int, in_sec: bool, budget: list) -> list:
    out = []
    for _ in range(rng.randint(1, 4)):
        if budget[0] <= 0:
            break
        budget[0] -= 1
        r = rng.random()
        leaf = depth <= 0
        if r < 0.25 or (leaf and r < 0.6):
            out.append(("call", rng.choice(TARGETS)))
        elif r < 0.32 or leaf:
            out.append(("decoy", rng.choice(DECOYS)) if rng.random() < 0.6 else ("sleep",))
        elif r < 0.47 and not in_sec:
            out.append(("asec", rng.choice(SECTIONS), gen_async(rng, depth - 1, True, budget)))
        elif r < 0.57:
            out.append(("task", gen_async(rng, depth - 1, False, budget)))
        elif r < 0.65:
            out.append(("gather", [gen_async(rng, depth - 1, False, budget)
                                   for _ in range(rng.randint(2, 3))]))
        elif r < 0.73:
            out.append(("to_thread", gen_sync(rng, depth - 1, False, budget)))
        elif r < 0.85:
            out.append(("await", gen_async(rng, depth - 1, in_sec, budget)))
        else:
            out.append(("sync", gen_sync(rng, depth - 1, in_sec, budget, True)))
    return out


def gen_program(seed: int) -> dict:
    rng = random.Random(seed)
    budget = [rng.randint(8, 40)]
    if seed % 3 == 2:
        if rng.random() < 0.5:
            return {"mode": "async_in_section", "section": rng.choice(SECTIONS),
                    "body": gen_async(rng, 4, True, budget)}
        return {"mode": "async", "body": gen_async(rng, 4, False, budget)}
    return {"mode": "sync", "body": gen_sync(rng, 4, False, budget)}


# -- the oracle ---------------------------------------------------------------------------------

def oracle(prog: dict) -> tuple[dict, dict]:
    """(expected union counts per opened section, Counter of ends per section)."""
    exp: dict = {}
    ends: dict = {}

    def opened(s, end):
        exp.setdefault(s, Counter())
        ends.setdefault(s, Counter())[end] += 1

    def credit(ctx, t, n=1):
        if ctx is not None and n:
            exp[ctx][t] += n

    def sync(nodes, ctx):
        for nd in nodes:
            k = nd[0]
            if k in ("call", "partial", "alias"):
                credit(ctx, nd[1])
            elif k == "gen":
                credit(ctx, "t1", nd[1])
            elif k in ("sec", "secraise"):
                opened(nd[1], "returned" if k == "sec" else "raised")
                sync(nd[2], nd[1])
            elif k == "thread":
                sync(nd[1], None)
            elif k in ("par", "pool"):
                for b in nd[1]:
                    sync(b, None)
            elif k == "deep":
                sync(nd[2], ctx)
            elif k == "exc":
                sync(nd[1], ctx)
            elif k == "loop":
                asy(nd[1], None)
            # decoy, genthread: nothing credited

    def asy(nodes, ctx):
        for nd in nodes:
            k = nd[0]
            if k == "call":
                credit(ctx, nd[1])
            elif k == "asec":
                opened(nd[1], "returned")
                asy(nd[2], nd[1])
            elif k == "task":
                asy(nd[1], None)
            elif k == "gather":
                for b in nd[1]:
                    asy(b, None)
            elif k == "to_thread":
                sync(nd[1], None)
            elif k == "await":
                asy(nd[1], ctx)
            elif k == "sync":
                sync(nd[1], ctx)

    if prog["mode"] == "sync":
        sync(prog["body"], None)
    elif prog["mode"] == "async":
        asy(prog["body"], None)
    else:
        opened(prog["section"], "returned")
        asy(prog["body"], prog["section"])
    return ({s: dict(c) for s, c in exp.items()}, {s: dict(c) for s, c in ends.items()})


# -- the interpreter ----------------------------------------------------------------------------

def interpret(prog: dict, cov, fx) -> None:
    def deep(n, fn):
        return fn() if n <= 0 else deep(n - 1, fn)

    def sync(nodes):
        for nd in nodes:
            k = nd[0]
            if k == "call":
                getattr(fx, nd[1])(1)
            elif k == "decoy":
                getattr(fx, nd[1])(1)
            elif k == "partial":
                functools.partial(getattr(fx, nd[1]), 1)()
            elif k == "alias":
                f = getattr(fx, nd[1])
                f(1)
            elif k == "gen":
                for _ in fx.gen_t1(nd[1]):
                    pass
            elif k == "sec":
                cov.run(nd[1], sync, nd[2])
            elif k == "secraise":
                def body(b=nd[2]):
                    sync(b)
                    raise _Boom()
                try:
                    cov.run(nd[1], body)
                except _Boom:
                    pass
            elif k == "thread":
                th = threading.Thread(target=sync, args=(nd[1],))
                th.start()
                th.join(60)
            elif k == "par":
                ths = [threading.Thread(target=sync, args=(b,)) for b in nd[1]]
                for th in ths:
                    th.start()
                for th in ths:
                    th.join(60)
            elif k == "pool":
                with ThreadPoolExecutor(max_workers=2) as ex:
                    for f in [ex.submit(sync, b) for b in nd[1]]:
                        f.result(60)
            elif k == "deep":
                deep(nd[1], lambda b=nd[2]: sync(b))
            elif k == "exc":
                try:
                    sync(nd[1])
                    raise _Boom()
                except _Boom:
                    pass
            elif k == "loop":
                asyncio.run(asy(nd[1]))
            elif k == "genthread":
                g = fx.gen_t1(nd[1])
                th = threading.Thread(target=lambda: [None for _ in g])
                th.start()
                th.join(60)

    async def asy(nodes):
        for nd in nodes:
            k = nd[0]
            if k in ("call", "decoy"):
                getattr(fx, nd[1])(1)
            elif k == "sleep":
                await asyncio.sleep(0)
            elif k == "asec":
                await cov.run_async(nd[1], asy, nd[2])
            elif k == "task":
                await asyncio.get_running_loop().create_task(asy(nd[1]))
            elif k == "gather":
                await asyncio.gather(*[asy(b) for b in nd[1]])
            elif k == "to_thread":
                await asyncio.to_thread(sync, nd[1])
            elif k == "await":
                await asy(nd[1])
            elif k == "sync":
                sync(nd[1])

    if prog["mode"] == "sync":
        sync(prog["body"])
    elif prog["mode"] == "async":
        asyncio.run(asy(prog["body"]))
    else:
        asyncio.run(cov.run_async(prog["section"], asy, prog["body"]))


# -- comparison ---------------------------------------------------------------------------------

def observed(rec: dict) -> tuple[dict, dict, list, int]:
    got, ends, amb = {}, {}, 0
    for s, openings in rec.get("sections", {}).items():
        c = Counter()
        for o in openings:
            for t, n in o.get("calls", {}).items():
                c[t.split(":", 1)[1]] += n
            amb += sum(o.get("ambiguous", {}).values())
            ends.setdefault(s, Counter())[o.get("end")] += 1
        got[s] = dict(c)
    return got, {s: dict(c) for s, c in ends.items()}, list(rec.get("problems", [])), amb


_NOTE = __import__("re").compile(r"\[V5:([A-Z_]+)\]")


def normalized(rec: dict) -> dict:
    """The implementation-independent content of a record, for N-version diffing: per section,
    the sorted multiset of openings (calls, ambiguous, end, note CODES); problem codes. Message
    wording, target provenance paths and the partial uncredited buckets are excluded."""
    secs = {}
    for s, openings in sorted(rec.get("sections", {}).items()):
        secs[s] = sorted(json.dumps({"calls": o.get("calls", {}), "ambiguous": o.get("ambiguous", {}),
                                     "end": o.get("end"),
                                     "notes": sorted(_NOTE.findall(" ".join(o.get("notes", []))))},
                                    sort_keys=True) for o in openings)
    return {"sections": secs,
            "problems": sorted(_NOTE.findall(" ".join(rec.get("problems", []))))}


def _commit_prereg(tmp: Path) -> Path:
    gates = {s: {"metric": "m", "op": ">=", "value": 0.5,
                 "exercises": [f"{FX}:{t}" for t in TARGETS]} for s in SECTIONS}
    spec = {"gates": gates, "outcomes": [{"when": {}, "verdict": "PASS"}],
            "smoke_verdict": "SMOKE"}
    p = tmp / "PREREG_fuzz.md"
    p.write_text("# fuzz\n\n```gates\n" + json.dumps(spec) + "\n```\n", encoding="utf-8")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=fuzz@local", "-c", "user.name=fuzz", "commit", "-qm", "f"]):
        subprocess.run(cmd, cwd=tmp, check=True)
    return p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1500)
    ap.add_argument("--seed-base", type=int, default=20260924)
    ap.add_argument("--control-no-cut", action="store_true",
                    help="positive control: after each trace starts, set the implementation's _STOP "
                         "(the dispatch-cut code object the hook reads on every event, per the "
                         "frozen spec) to None; the fuzzer MUST then find disagreements")
    args = ap.parse_args()
    import styxx.protocol as P
    from styxx.protocol import Experiment, coverage_trace

    work = Path(tempfile.mkdtemp(prefix="v5efuzz_"))
    (work / f"{FX}.py").write_text(FIXTURE, encoding="utf-8")
    sys.path.insert(0, str(work))
    fx = __import__(FX)
    originals = {n: getattr(fx, n).__code__ for n in TARGETS + ["t0_preclone", "p_decoy", "w_decoy"]}
    pdir = work / "prereg"
    pdir.mkdir()
    exp = Experiment(_commit_prereg(pdir))

    disagreements, leftovers, modes = [], [], Counter()
    dump = (open(os.environ["STYXX_V5_FUZZ_TRACES"], "w", encoding="utf-8")
            if os.environ.get("STYXX_V5_FUZZ_TRACES") else None)
    t_start = time.time()
    for i in range(args.n):
        seed = args.seed_base + i
        prog = gen_program(seed)
        modes[prog["mode"]] += 1
        want, want_ends = oracle(prog)
        try:
            with coverage_trace(exp) as cov:
                if args.control_no_cut:
                    P._STOP = None
                interpret(prog, cov, fx)
            rec = cov.record()
            got, got_ends, problems, amb = observed(rec)
            if dump:
                dump.write(json.dumps({"seed": seed, **normalized(rec)}, sort_keys=True) + "\n")
            ok = (got == want and got_ends == want_ends and not problems and amb == 0)
            detail = None if ok else {"want": want, "got": got, "want_ends": want_ends,
                                      "got_ends": got_ends, "problems": problems[:3],
                                      "ambiguous": amb}
        except Exception as e:                                    # noqa: BLE001
            ok, detail = False, {"raised": f"{type(e).__name__}: {e}"[:400]}
        left = []
        if sys.getprofile() is not None:
            left.append("sys.getprofile() is set")
            sys.setprofile(None)
        for n, c in originals.items():
            if getattr(fx, n).__code__ is not c:
                left.append(f"{n}.__code__ not restored")
        for reg in ("_MINTED", "_BY_FN", "_ANCHORS", "_THREADS"):
            if getattr(P, reg, {}):
                left.append(f"{reg} not empty")
        if getattr(P, "_ACTIVE", 0):
            left.append("_ACTIVE != 0")
        if left:
            leftovers.append({"seed": seed, "leftover": left})
        if not ok:
            disagreements.append({"seed": seed, "mode": prog["mode"],
                                  "program": json.dumps(prog)[:600], **detail})
    if dump:
        dump.close()
    secs = round(time.time() - t_start, 2)
    impl = Path(P.__file__)
    out = {
        "fuzzer": "papers/first-afference/fuzz_v5e.py",
        "fuzzer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "impl_sha256": hashlib.sha256(impl.read_bytes()).hexdigest(),
        "impl_path": str(impl),
        "python": sys.version.split()[0],
        "seed_base": args.seed_base,
        "mode": "control_no_cut" if args.control_no_cut else "oracle",
        "fuzz_n_programs": args.n,
        "modes": dict(modes),
        "fuzz_oracle_disagreements": len(disagreements),
        "fuzz_leftovers": len(leftovers),
        "seconds": secs,
        "disagreements": disagreements[:25],
        "leftover_detail": leftovers[:25],
    }
    dest = (Path(os.environ["STYXX_V5_RESULT_OUT"]) if os.environ.get("STYXX_V5_RESULT_OUT")
            else HERE / ("protocol_v5e_fuzz_control_no_cut.json" if args.control_no_cut
                         else "protocol_v5e_fuzz.json"))
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"{args.n} programs {dict(modes)} | disagreements {len(disagreements)} | "
          f"leftovers {len(leftovers)} | {secs}s -> {dest}")
    for d in disagreements[:5]:
        print("  ", json.dumps(d)[:400])
    return 0


if __name__ == "__main__":
    sys.exit(main())
