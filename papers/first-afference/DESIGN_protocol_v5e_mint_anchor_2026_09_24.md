# protocol v5e: minted code identity and stack-anchor attribution (synthesis)

**Basis.** Both judges chose the "mint-and-anchor" design, and this spec starts from it. It adds the judges' grafts and corrects every claim a judge showed to be false. Where the judges disagreed, soundness decided:

- **Adopted: the asyncio `Handle._run` dispatch cut.** Judge 1 wanted it; judge 2 preferred to keep the breadth. The cut wins on soundness.
- **Adopted: provenance.** Judge 1 proposed checking `__module__`. This spec checks `__globals__` identity instead, which is stronger (see Target identity).
- **Adopted: open-time refusals are recorded in the trace.**
- **Adopted: counts are lower bounds.** Every condition that can only lose calls is now a note.
- **Adopted from judge 2:** aliases are accepted; paths may step through an instance's own `__dict__`; a module's PEP 562 `__getattr__` is followed; a C cache wrapper is traced through its body (restricted form); uncredited-diagnostic buckets and an honest NOT_EXERCISED message; exam hazard sweeps paired with detection mutants.
- **Kept against judge 2:** CODE_SWAPPED stays a refusal. A swapped `__code__` is the only route to over-credit.
- **Declined:** the sys.monitoring backend for 3.12+, which both judges marked optional. Two backends would make expected outcomes depend on the Python version and double the exam matrix. It is deferred to a later protocol version.

**Verified in scratch.** Scratch prototype: `/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/design/synth/v5f.py` (about 440 lines including scoring). Batteries s1–s8 in the same directory ran on 3.10.20, 3.11.15, 3.12.3 and 3.13.12:

- The outputs are identical across versions except for the cProfile case, which the spec keys by version.
- The P1 retro is exact on all four versions.
- The stress run (s5) recorded exact counts with 0 cross-credit, twice on each version.
- The SIGALRM verdict (s6) was PASS 20/20 on each version.

---

## Target identity

### Rule (one sentence)
A frame counts for declared target T iff `frame.f_code is M_T` and `frame.f_globals is F_T.__globals__`. Here F_T is T's traced function and M_T is a fresh code object the tracer created at entry with `F_T.__code__.replace()` and published only by assigning it to `F_T.__code__`.

### Resolution (at `__enter__`, every target, before anything is touched)
The grammar `module:Q.u.a.l` is unchanged: `_TARGET_RE.fullmatch`, ASCII only, no duplicates (DECL). Resolution runs these steps:

1. `mod = importlib.import_module(module)`. If it raises any `Exception` (including SyntaxError), refuse **UNRESOLVED**.
2. For each step `part`, with `obj` the object reached so far:
   - **`obj` is a module.** This is allowed only as the first step. A module reached later refuses **INSTANCE_PATH** ("put the full module path before the colon"). Read `vars(obj)[part]`. If the name is absent and `"__getattr__" in vars(obj)` (PEP 562), call it once. If it raises, refuse **UNRESOLVED**. If the name is absent and there is no `__getattr__`, refuse **UNRESOLVED**, with a message naming unimported submodules.
   - **`obj` is a class.** Read `vars(obj)[part]`. If the name is found only in a base's `__dict__`, refuse **INHERITED**; if it is found nowhere, refuse **UNRESOLVED**.
   - **Anything else.** Read `d = object.__getattribute__(obj, "__dict__")` inside a try, with no `getattr` and no `__getattr__`. If the read fails, if `type(d) is not dict`, or if `part not in d`, refuse **INSTANCE_PATH**. The message says the attribute comes from the class and names the class to declare. This admits SimpleNamespace and registry objects; `default_model.fit` still refuses.
3. Unwrap a `staticmethod` or `classmethod` to its `__func__`.
4. Choose the **traced function F_T**:
   - If `type(obj) is types.FunctionType`, then F_T = obj. Nothing is ever unwrapped: a `functools.wraps` wrapper *is* the target.
   - If `type(obj) is functools._lru_cache_wrapper` (C `lru_cache` or `cache`), let `body = obj.__dict__.get("__wrapped__")`. It must be a FunctionType; otherwise refuse **NOT_A_FUNCTION**. The body must also not be a value in `vars(mod)`, nor in the namespace that held `obj`; otherwise refuse **NOT_A_FUNCTION** ("the body is also bound as X; declare that name"). Then F_T = body. The target is defined as the cached body: misses count and hits do not.
   - Anything else refuses **NOT_A_FUNCTION**. That includes builtins, C/Cython/numba callables, `partial`, `property`/`cached_property`, bound methods, `singledispatchmethod`, MagicMock and class-based `update_wrapper` wrappers.
5. **Provenance (FOREIGN_DEFINITION).** The declared object is accepted iff one of the following has `__globals__ is mod.__dict__`:
   - the object itself, when it is a FunctionType;
   - any link of its own-`__dict__` `__wrapped__` chain. The walk steps only through FunctionType and cache-wrapper links, stops after at most 16 hops, and is cycle-detected. It never uses `getattr`.

   Otherwise refuse **FOREIGN_DEFINITION**, naming where the code was defined.
   - This closes judge 1's X1: a stub or `monkeypatch` lambda from a test module bound before the trace; `mock.patch(autospec=True)`, whose funcopy is exec'd in mock's private dict; a re-export (declare the defining module); a decorator product without `wraps` defined elsewhere; functions exec'd in a fresh namespace.
   - A `wraps` wrapper from any module passes through its chain. So does a singledispatch dispatcher.
   - `__globals__` is used rather than `__module__` because `__module__` is a writable string that anyone can set and `wraps` copies. `__globals__` is read-only and fixed when the function is created. Case X30 fails a `__module__`-based implementation.
6. **Aliases are accepted.** If two declared names resolve to one F_T, they share one mint, and every credited hit credits all of those names. Provenance lives in the trace, and the reason code ALIAS does not exist.
7. **Resolve everything, then touch anything.** If any target refuses, no code object is minted (case X33).

### Minting
This happens under `_LOCK`, after every target has resolved:

- For each distinct F_T, look it up in `_BY_FN` (keyed by `id(F_T)`, and checked with `m.fn is F_T`).
  - If an enclosing tracer already minted it and `F_T.__code__ is not m.code`, refuse **CODE_SWAPPED** at entry, before anything is minted.
  - Otherwise, if no mint exists, create `_Mint(fn, original=fn.__code__, code=fn.__code__.replace(), globals=fn.__globals__)`, assign `fn.__code__ = m.code`, and register the mint in `_MINTED[id(m.code)]` and `_BY_FN[id(fn)]`.
  - Append the tracer to `m.tracers`, which is an immutable tuple that writers replace.
- Nested and concurrent tracers share one mint. The original code is restored when the last tracer holding the mint exits, and only if `fn.__code__ is m.code` at that moment.

### Tripwires (recorded, refuse every declaring gate)
- **CLONE_CALLED.** M_T ran with `f_globals is not F_T.__globals__`: `FunctionType(T.__code__, other)` or `exec(T.__code__, other)`. The call credits nothing.
- **CLONE_ALIVE.** At exit, `sys.getrefcount(M_T) - 2 - (F_T.__code__ is M_T) > 0`. Only then does the tracer run `gc.get_referrers(M_T)`, and it records the problem if that scan finds a FunctionType other than F_T. Live generators, frames and tracebacks of T are not FunctionTypes and do not trigger it.
- **CODE_SWAPPED.** At exit, `F_T.__code__ is not M_T`. This catches hot reload, harness swaps, and `U.__code__ = T.__code__` followed by a later swap.

### Why class A cannot reopen, and the one door that remains
A frame is linked to the function it runs only through its code object and its globals. CPython runs a code object C in a frame only by calling a function whose `__code__` is C, or through `exec`/`eval` of C. A function acquires C only in three ways:

- `MAKE_FUNCTION` on a compiled constant;
- `FunctionType(C, ...)`;
- `__code__` assignment.

M_T is in no `co_consts`. So factories, closures with any defaults, decorators with or without `wraps`, per-call siblings, runtime decoration, dataclass siblings, vendored or exec'd module copies, pre-trace clones, `copy`/`deepcopy` (functions are atomic) and pickle (by reference) all run *other* code objects. Because nothing is unwrapped, no two distinct callables ever map to one observed code object; that many-to-one mapping was the root of R2-D2 and R3-D1.

**The remaining door**, which is never claimed closed: during the trace, code reads M_T (from `T.__code__`, from a live T frame's `f_code`, from `gi_code`, or from a traceback) and then does one of these:
- builds a function with **T's own globals**, calls it, and drops it before exit;
- runs `exec(M_T, T.__globals__)`;
- assigns `U.__code__ = M_T` and swaps it back before exit.

A live clone is caught by CLONE_ALIVE, other globals by CLONE_CALLED, and a swap left in place by CODE_SWAPPED. **Provenance residual:** a stub *defined in the declared module*, or a wraps-stamped stub (`functools.wraps(real)(fake)`), bound at the name before the trace passes FOREIGN_DEFINITION. Both residuals are in Stated limits.

### Claims corrected from the base design
- **"Module attribute rebound to a mock → NOT_EXERCISED" (judge 1).** This held only for rebinding *during* the trace (X53). Rebinding before the trace is now FOREIGN_DEFINITION (X26–X30), with the residual above.
- **"Only plain functions can be declared."** Cache wrappers are now accepted via their body, instance-own-dict paths and PEP 562 are accepted, and aliases are accepted. Each of these rules has a case that fails if the rule is deleted (V07, V08, V10, V02).

---

## Attribution

### Rule (one sentence)
A counted frame is credited to opening O iff O's anchor is registered (O is open) and is met on the frame's `f_back` chain before the first frame whose `f_code is asyncio.events.Handle._run.__code__`, and no other open opening of O's tracer is met there. The anchor is the frame of the `cov.run(...)` call or the `cov.run_async(...)` coroutine that opened O.

### Sections are calls
```python
result = cov.run(section, fn, /, *args, **kwargs)              # sync
result = await cov.run_async(section, afn, /, *args, **kwargs) # coroutine frame is the anchor
```
- Opening and closing happen in one frame, in its `finally`, so they are LIFO per stack by construction. There is no `with cov.section(...)`, no ContextVar and no foreign-context exit.
- An event loop must run *outside* the section: write `asyncio.run(cov.run_async(name, main))`. The form `cov.run(name, asyncio.run, main())` counts nothing, because every task step is cut at `Handle._run`. The `dispatched` diagnostic shows those calls.
- A task inside any loop, including a loop that runs inside another section, may open its own `run_async` section.

### At open (raised before fn runs, and recorded; see Mechanism)
The checks run in this order:
1. **TRACE_INACTIVE**: the tracer is not active.
2. **UNDECLARED_SECTION**: no gate declares this section.
3. **NESTED_SECTION**: an open opening of the *same* tracer is on the opener's `f_back` chain before the cut. Other tracers may nest, and each credits its own openings.
4. **FOREIGN_PROFILER**: `sys.getprofile()` is not None and is not the styxx hook. The foreign profiler is never called, chained, restored or replaced.

The same section name may be open any number of times at once, on different stacks.

### At a hit (a `'call'` event whose `f_code` is a minted code object)
- The hook walks `f_back`, collecting registered anchors, until it reaches the cut or the root.
- For each tracer holding the mint:
  - **Exactly one** of its openings found: that opening's `calls[name] += 1` for every declared name of T.
  - **Two or more** found: each gets `ambiguous[name] += 1`, and nothing is credited. This is reachable only when a manually driven coroutine of one opening is resumed inside another opening.
  - **None** found: the tracer's per-thread `uncredited` counter is incremented, under `dispatched` if the walk hit the cut and `unattributed` otherwise.

### At close and at exit
- **Close** (in `run`'s `finally`, on return and on raise) deregisters the anchor first, then records `end = "returned" | "raised"`. It may add a note: **THREAD_HOP** if the opening closed on another thread, **PROFILER_LOST** if the hook is not ours or the thread's install epoch changed.
- **Tracer exit** proceeds in this order:
  1. It sets `_by_code = {}` first, so no credit is possible after exit.
  2. Every still-open opening is detached with end `"open"` and the note **OPEN_AT_EXIT**; a later close of it is a no-op.
  3. It checks the tripwires.

### What score credits
- A gate is judged on the **union of `calls` over all openings of its section**, whatever their `end`.
- Notes (PROFILER_LOST, THREAD_HOP, OPEN_AT_EXIT, LAZY_RESULT) and `end != "returned"` **never refuse**. They are printed in the NOT_EXERCISED message. This makes counts lower bounds: none of these conditions can create a credit, because a credit needs a registered anchor that is executing on the live chain.
- `ambiguous` and `uncredited` never count.
- Every entry in `problems` (the open-time refusals plus the tripwires) refuses **every declaring gate** scored against the trace, whether or not the harness swallowed the exception.

### Why class B cannot reopen through the runtime, and the door that stays open
A frame's `f_back` chain holds only frames on the same thread that are executing and transitively waiting on this call.

- Threads, pool workers, executors, `to_thread`, library daemon threads and grandchildren all start at their own bootstrap frame.
- Every task step, callback, `call_soon_threadsafe` handle and `run_coroutine_threadsafe` submission is executed by `Handle._run`, which the walk does not cross.
- No inherited state is read, whether ContextVar, thread-start record or pool lifetime, so no context copy can carry credit anywhere.
- After a close, the anchor is not executing.

So no *runtime-provided* hand-off can move credit between sections. **Correction of the base design's claim** that "concurrent sections cannot cross-credit" (judges 1 and 2): work that another gate supplies *as data* and that a section's own stack executes is credited to that section. Examples are a queue drained inline, a long-lived consumer that opened its own opening of the section (X4), non-asyncio schedulers run inside a section, and generators resumed there. The stack shows *where* code ran, not *who* asked for it. This is stated limit L-WHERE, and the exam pins it (R01, R02, R09, R10). A *sectioned* foreign job on a sectioned consumer fails closed with NESTED_SECTION (X77).

---

## Mechanism and lifecycle

### Module state
```python
_TRACER_ID = "styxx.protocol.coverage_trace/2"
_CACHE_WRAPPER = type(functools.lru_cache(None)(lambda: 0))
_LOCK = threading.RLock()        # __enter__/__exit__/_open/_close only. Never the hook, never record().
_MINTED = {}   # id(M) -> _Mint           (the _Mint holds M, so the id cannot be reused)
_BY_FN  = {}   # id(F_T) -> _Mint         (holds F_T)
_ANCHORS = {}  # id(anchor frame) -> _Opening (the opening holds the frame until close/exit)
_THREADS = {}  # thread ident -> [open openings on that thread, install epoch]
_EPOCH = itertools.count(1)      # global, so a recreated _THREADS entry never reuses an epoch
_ACTIVE = 0                      # tracers between a completed __enter__ and the start of __exit__
_STOP = None                     # asyncio.events.Handle._run.__code__, read in __enter__ after minting
```
- `_Mint` fields: `fn, original, code, globals, tracers` (a tuple, replaced and never mutated).
- `_Opening` fields: `tracer, section, frame, tid, epoch, calls{}, ambiguous{}, end, notes[]`.
- Per tracer: `_state` (one of new, active, exiting, exited), `_by_code: id(M) -> tuple(names)`, `_prov`, `_openings`, `_problems`, `_clone_called`, and `_uncredited` (a map from tid to `(dispatched{}, unattributed{})`, single-writer per thread).

### The hook: one module-level function with no try/except, no lock, and no handler
```python
def _hook(frame, event, arg):
    tid = threading.get_ident()
    if not _ACTIVE or tid not in _THREADS:
        sys.setprofile(None); return                 # self-removal
    if event != "call": return
    code = frame.f_code
    m = _MINTED.get(id(code))
    if m is None or m.code is not code: return       # identity, never equality
    tracers = m.tracers
    if frame.f_globals is not m.globals:             # CLONE_CALLED; credits nothing
        for t in tracers: t._clone_called.add(id(code))
        return
    found, cut, f = [], False, frame.f_back
    while f is not None:
        if f.f_code is _STOP: cut = True; break
        o = _ANCHORS.get(id(f))
        if o is not None and o.frame is f: found.append(o)
        f = f.f_back
    for t in tracers:
        names = t._by_code.get(id(code))
        if not names: continue
        mine = [o for o in found if o.tracer is t]
        if len(mine) == 1: bump(mine[0].calls, names)
        elif mine:
            for o in mine: bump(o.ambiguous, names)
        else: bump(t._uncredited_for(tid)[0 if cut else 1], names)
```
Why no exception handling in the hook:

- An exception raised in the hook, or while CPython enters it, propagates as CPython defines. That covers signal-handler exceptions, KeyboardInterrupt and RecursionError. CPython then drops the hook on that thread. The loss is recorded as a PROFILER_LOST note at close, and afterwards that thread only under-counts.
- Per-opening counters are single-writer, because an anchor is on only one stack at a time.
- Calls made while the profile function is running are not observed, because CPython disables profiling inside a profiler. So finalizers triggered by the hook's own allocations cannot re-enter it.

### `__enter__`
1. If the state is not `new`, refuse **REENTRY**. This refusal is recorded if the tracer was ever entered.
2. Run `import asyncio.events`, a one-time cost.
3. Resolve every target (see Target identity).
4. Under `_LOCK`, do the entry CODE_SWAPPED check for all targets, then mint.
5. Set `_STOP = asyncio.events.Handle._run.__code__`, run `_ACTIVE += 1`, and set the state to `active`.

### `run`, `run_async`, `_open`, `_close`
```python
def run(self, section, fn, /, *args, **kwargs):
    o = self._open(section, sys._getframe())        # registration is _open's LAST statement
    end = "raised"
    try:
        result = fn(*args, **kwargs); end = "returned"
    finally:
        self._close(o, end)                          # never raises
    if isinstance(result, (types.CoroutineType, types.GeneratorType, types.AsyncGeneratorType)):
        o.notes.append("[V5:LAZY_RESULT] ...")       # its body runs after the section closed
    return result

async def run_async(self, section, afn, /, *args, **kwargs):   # same, with `await afn(...)`

def _open(self, section, anchor):
    # checks in order: TRACE_INACTIVE, UNDECLARED_SECTION,
    # NESTED_SECTION (walk anchor.f_back until the cut or the root; same tracer only),
    # FOREIGN_PROFILER (under _LOCK). Each refusal goes through self._fail(code, msg),
    # which appends str(err) to self._problems when the state is not "new", and is raised.
    with _LOCK:
        st = _THREADS.setdefault(tid, [0, 0])
        if sys.getprofile() is None:
            st[1] = next(_EPOCH); sys.setprofile(_hook)
        st[0] += 1
        o = _Opening(self, section, anchor, tid, st[1]); self._openings.append(o)
        _ANCHORS[id(anchor)] = o
    return o

def _close(self, o, end):
    with _LOCK:
        if o.frame is None: return                   # detached by tracer exit
        _ANCHORS.pop(id(o.frame), None); o.frame = None
        st = _THREADS.get(o.tid)
        if tid != o.tid: o.notes.append("[V5:THREAD_HOP] ...")
        elif sys.getprofile() is not _hook or st is None or st[1] != o.epoch:
            o.notes.append("[V5:PROFILER_LOST] ...")
        if st is not None:
            st[0] -= 1
            if st[0] <= 0:
                del _THREADS[o.tid]
                if tid == o.tid and sys.getprofile() is _hook: sys.setprofile(None)
        o.end = end
```

### `__exit__` (never raises; always returns False)
All of this runs under `_LOCK`:

1. Set the state to `exiting`, run `_ACTIVE -= 1` and set `self._by_code = {}`. The steps that stop credit come first.
2. For each opening still open: add the OPEN_AT_EXIT note, deregister its anchor, set `frame = None`, and decrement its thread's count, deleting the entry at 0.
3. Convert `_clone_called` into CLONE_CALLED problems.
4. For each distinct mint:
   - drop this tracer from `m.tracers`;
   - if `fn.__code__ is not m.code`, record CODE_SWAPPED; otherwise, if no tracers remain, restore the original code;
   - if no tracers remain, unregister the mint;
   - run the refcount check, then the gated `gc.get_referrers` scan, giving CLONE_ALIVE.
5. If `_ACTIVE == 0` and the hook is this thread's profiler, remove it.
6. Set the state to `exited` as the last statement.

If an exception interrupts exit, the state stays `exiting` and `record()` refuses **TRACE_INCOMPLETE**. The minted code may stay installed; it is equal code and harmless.

### `record()` and the trace schema (exact)
`record()` takes no lock and only copies. On a `new` or `active` tracer it refuses **TRACE_ACTIVE**; on an `exiting` tracer it refuses **TRACE_INCOMPLETE**.
```text
{"tracer": "styxx.protocol.coverage_trace/2",
 "gates_sha256": "<hex>",
 "targets":   {"<module:qualname>": "<co_filename>:<co_firstlineno>"},      # provenance only, unchecked
 "sections":  {"<section>": [{"calls": {tgt: int>=1}, "ambiguous": {tgt: int>=1},
                               "end": "returned"|"raised"|"open", "notes": ["[V5:<NOTE>] ..."]}, ...]},
 "uncredited": {"dispatched": {tgt: int>=1}, "unattributed": {tgt: int>=1}},  # partial; see limits
 "problems":  ["[V5:<RECORDED>] ...", ...]}
```
- `<NOTE>` is one of PROFILER_LOST, THREAD_HOP, OPEN_AT_EXIT, LAZY_RESULT.
- `<RECORDED>` is one of REENTRY, TRACE_INACTIVE, UNDECLARED_SECTION, NESTED_SECTION, FOREIGN_PROFILER, CLONE_CALLED, CLONE_ALIVE, CODE_SWAPPED.

### `score()` for a declaring gate, in this order
1. **NO_TRACE**: the result is not a dict, or `dict.get(result, "coverage_trace")` is not an exact dict.
2. **WRONG_TRACER**: the tracer id is not `/2`. Every `/1` trace refuses here.
3. **BAD_TRACE**, in one pass before anything is read. Every type check is exact (`type(x) is ...`):
   - the top-level key set is exactly the six keys;
   - `targets` is a dict of str to str;
   - `sections` is a dict of str to a non-empty list;
   - each opening is a dict with exactly the four keys, `end` is in the enum, and `notes` is a list of str, each matching `^\[V5:([A-Z_]+)\] ` with a known note code;
   - `uncredited` is a dict with exactly its two keys;
   - every count dict (calls, ambiguous, dispatched, unattributed) is a dict with str keys;
   - `problems` is a list of str, each with a known recorded code.
4. **STALE_TRACE**: `gates_sha256` mismatch.
5. **TARGET_SET**: `sorted(targets)` is not the declared set.
6. **BAD_COUNT**: any count anywhere whose key is not a declared target, or whose value is not an int ≥ 1 (bool is refused).
7. **Recorded problem**: if `problems` is non-empty, refuse with the first problem's own code; the message lists all of them.
8. **SECTION_ABSENT**: the gate's section key is missing.
9. **NOT_EXERCISED**: a declared target is missing from the union of `calls`. The message reads "not executed on the stack of any opening of section S". It lists the notes, the non-`returned` ends, and the `dispatched`/`unattributed` counts for the missing targets. It also carries the fixed sentence: "work on other threads, pools, executors or asyncio tasks is credited only to a section that work opens itself".

`check_metrics` keeps its existing loop. It reports `usable: False` with the refusal text and never raises, including for `None`, `[]`, `'s'` and `5`.

### Cost
The figures below were measured on the base prototype; the implementation must re-measure them.

| Operation | Cost |
|---|---|
| Profile hook, per event, on threads with an open opening | about 0.4 µs |
| f_back walk, per hit at depth 30 | about 3–5 µs (100k hits: 0.33–0.46 s, against 0.11–0.14 s today) |
| gc at resolution or at close | none |
| One close on a 1M-object heap | 0.02–0.05 ms (today: 100–122 ms) |
| Exit | 0.01 ms, plus about 17–19 ms for the gated scan when a live generator or traceback holds M_T |
| First `__enter__` in a process | imports asyncio |

### Versions
- Executed on 3.10–3.13, with identical batteries apart from cProfile. On 3.12 and later, cProfile uses sys.monitoring and coexists with the tracer.
- 3.9 was not executed. It uses only APIs available since 3.8, so it is expected to behave like 3.10.
- 3.14 is not supported until `Handle._run` and the frame model are re-validated.
- Free-threaded builds are untested.

---

## Reason codes

| code | when it fires | effect |
|---|---|---|
| DECL | parse: `exercises` is not a non-empty list of ASCII `module:qualname` (fullmatch), or has duplicates | raise |
| SECTION_DECL | parse: `section` without `exercises`, or not a non-empty ASCII str | raise |
| NOTHING_DECLARED | `coverage_trace(exp)` when no gate declares `exercises` | raise |
| REENTRY | `__enter__` on a tracer that is not new | raise; recorded if the tracer was entered before |
| UNRESOLVED | entry: the import raised; the name is absent with no module `__getattr__`; the module `__getattr__` raised; a class lacks the name everywhere | raise; nothing minted |
| INHERITED | entry: a class step whose name exists only in a base's `__dict__` | raise |
| INSTANCE_PATH | entry: a module after the colon; a non-class, non-module step whose own `__dict__` is missing or lacks the name | raise |
| NOT_A_FUNCTION | entry: the object is not FunctionType, a staticmethod/classmethod of one, or a C cache wrapper with a FunctionType body not bound elsewhere in the namespace | raise |
| FOREIGN_DEFINITION | entry: neither the object nor any link of its own-dict `__wrapped__` chain has `__globals__ is module.__dict__` | raise |
| CODE_SWAPPED | entry: an enclosing trace's M_T is no longer `T.__code__`; exit: `T.__code__ is not M_T` | entry: raise. Exit: recorded, and refuses every declaring gate |
| TRACE_INACTIVE | `run`/`run_async` on a tracer that is not active | raise; recorded if entered before |
| UNDECLARED_SECTION | open: no gate declares the section | raise + recorded |
| NESTED_SECTION | open: an open opening of the same tracer is on the opener's chain before the dispatch cut | raise + recorded |
| FOREIGN_PROFILER | open: `sys.getprofile()` is non-None and not the styxx hook; the profiler is left untouched | raise + recorded |
| CLONE_CALLED | hit: M_T ran with foreign `f_globals` | recorded at exit |
| CLONE_ALIVE | exit: an unexplained ref to M_T, and gc finds another FunctionType holding it | recorded |
| TRACE_ACTIVE | `record()` on a new or active tracer | raise |
| TRACE_INCOMPLETE | `record()` after an `__exit__` that did not finish | raise |
| NO_TRACE | score: the result is not a dict, or the trace is absent or not a dict | refuse |
| WRONG_TRACER | score: the tracer id is not `/2` | refuse |
| BAD_TRACE | score: any schema clause fails, including unknown note or problem codes | refuse |
| STALE_TRACE | score: `gates_sha256` mismatch | refuse |
| TARGET_SET | score: the trace's target set is not the declared set | refuse |
| BAD_COUNT | score: a count key is not a declared target, or a value is not an int ≥ 1 | refuse |
| *(recorded code)* | score: `problems` is non-empty | every declaring gate refuses with the first recorded code |
| SECTION_ABSENT | score: no opening of the gate's section | refuse |
| NOT_EXERCISED | score: a declared target is missing from the union of the section's `calls` | refuse |
| note PROFILER_LOST | close: the hook is not ours, or the thread's install epoch changed | never refuses |
| note THREAD_HOP | close: the opening closed on another thread | never refuses |
| note OPEN_AT_EXIT | exit: the opening is still open (`end: "open"`) | never refuses |
| note LAZY_RESULT | `run()` got a coroutine, generator or async generator back from fn | never refuses |
| RETIRED | SHARED_CODE, NO_CODE (now NOT_A_FUNCTION), THREAD_OUTLIVES, HOOK_FAILED, PROFILER_REPLACED (now the PROFILER_LOST note), EXIT_ORDER, SECTION_CONTEXT. Never adopted: ALIAS and SECTION_UNFINISHED (base design), SECTION_FORM, CARRY_OUTSIDE and MONITOR_BUSY (v5m), NESTED_CODE and SHARED_ROUTE (lower-bound) | — |

---

## What is removed from v5d

- **Sharing scans.** `_code_holders`, `_wrappers_of` and `_sharing_problem`, with every `gc.collect()` and `gc.get_referrers` pass at resolution and at each section close, and SHARED_CODE at entry and at close.
- **Unwrapping.** `inspect.unwrap` and every `__wrapped__` follow used for identity. `__wrapped__` survives only as a provenance walk and as the cache-wrapper body.
- **Module steps by `inspect.getattr_static`.** Replaced by `vars()` plus the explicit PEP 562 fallback.
- **Frame identity.** `_identity` (globals, freevars and closure cells read through `f_locals`) and the `impostors` bucket.
- **Code provenance.** marshal/sha256 code provenance in the trace; the trace now records `file:line` instead.
- **Section context.** `contextvars` section slot (`_cv`), `_effective`/`_effective_section`, and via-context/via-thread attribution.
- **Thread tracking.** `_THREAD_START_CODE` interception of `Thread.start`, `_thread_section`, THREAD_OUTLIVES and the `is_alive()` scan.
- **Buckets.** The name-keyed `_open` counter; the thread-inherited `ambiguous`, `after_close` and `unsectioned` buckets. Replaced by per-opening `ambiguous` and per-tracer `uncredited`.
- **Profiler handling.** `threading.setprofile`/`getprofile` and `_thread_profile`; the `_Hook` class with `prev` chaining; `_skip_exited`, `_hook_chain_has_self`, chained-profiler restore and EXIT_ORDER.
- **Hook failure handling.** `except Exception` in the hook and the sticky `_hook_failed`/HOOK_FAILED.
- **Locking.** The non-reentrant `self._lock`, which was taken in the hook and in `record()`.
- **Section API.** The `@contextmanager section()`, SECTION_CONTEXT, `_refuse_at_close`, and the unread `close_refusals`. There are no close-time refusals any more.
- **Obsolete reason codes.** PROFILER_REPLACED and NO_CODE.
- **Old tracer id.** `coverage_trace/1` is no longer accepted: committed v5, v5c and v5d results keep their verdicts as history, and their traces refuse WRONG_TRACER under v5e.
- **The v5d exam as a v5e exam.** The frozen exam (`run_protocol_v5d.py`) is not reusable. v5e needs its own prereg with a frozen runner hash.

---

## Finding closure

**Status values:**
- **CLOSED_S**: closed structurally.
- **CLOSED_P**: closed by patch.
- **LIMIT**: disclosed as a limit.
- **N/A**: not applicable.

Case ids refer to the exam section.

| id | status | how |
|---|---|---|
| R1-B1 shared code object | CLOSED_S | Frames are matched against per-function minted code, so siblings run the original code (X40, X41). Residual: an in-trace same-globals clone of M_T (L-CLONE; R03, R04), with CLONE_ALIVE and CLONE_CALLED tripwires (X55–X58) |
| R1-B2 equality not identity | CLOSED_S | `id` lookup plus `is` against a mint the registry holds (X45–X47) |
| R1-B3 global section slot | CLOSED_S for runtime hand-offs | Credit needs the opener's anchor on the live chain before the dispatch cut (X60–X62). User-level hand-off is L-WHERE (R01, R02) |
| R1-B4 C profiler crash/destroyed | CLOSED_S | FOREIGN_PROFILER at open; the foreign profiler is never called or replaced (X80, X81; V33 on ≥3.12) |
| R1-D1 non-LIFO/reentry leaks | CLOSED_S | Sections are calls; one shared hook; refcounted mints; REENTRY (V15–V17, X32) |
| R1-D2 resolution crashes | CLOSED_P | Any Exception from import or module `__getattr__` becomes UNRESOLVED. Nothing is unwrapped for identity. The provenance walk is bounded, cycle-detected and runs no user code (X10–X13) |
| R1-D3 non-string trace keys | CLOSED_P | Exact-type schema validation in one pass before reading (X96–X108, X111–X115) |
| R1-D4 undisclosed over-blocking | LIMIT | The Over-blocking list. Pre-existing and `_thread` threads, parallel sections and pools now work when each job opens its own section (V21, V22) |
| R1-N2 MRO/inherited, regex | CLOSED_P | Own-dict class steps; fullmatch (X14, X03) |
| R2-B1 runtime no-wraps decoration | CLOSED_S | The runtime product runs the decorator's original code (X42) |
| R2-B2 pool shared by concurrent sections | CLOSED_S | A pool stack never holds another section's anchor (X63). A sectioned long-lived consumer is L-WHERE (R01) |
| R2-B3 thread hook persists | CLOSED_S | No `threading.setprofile`; the last close removes the hook; the hook self-removes (V31, per-case leftover check) |
| R2-D1 instance path | CLOSED_P | Instance steps read the own `__dict__` only. `default_model.fit` refuses (X15); SimpleNamespace passes (V08) |
| R2-D2 wraps siblings | CLOSED_S | No unwrap: each wrapper has its own mint (X50) |
| R2-D3 undisclosed over-blocking (pools, executors) | LIMIT | Changed shape: jobs open their own sections (V21, V23); uncarried work never counts (X72, X73) |
| R2-D4 RecursionError in hook | CLOSED_S | No handler. The drop is a note and the verdict depends only on calls made (V27) |
| R2-D5 thread hook leaks on error paths | CLOSED_S | Close runs in `run`'s `finally` (V25 plus the leftover check) |
| R2-D6 escapes | CLOSED_S / CLOSED_P | Foreign-context exit: no ContextVar exists, so it cannot occur. check_metrics on a non-dict reports instead of raising (X117) |
| R3-B1 factory products/defaults | CLOSED_S | Products run the factory's constant code (X43, X44) |
| R3-B2 asyncio tasks inherit context | CLOSED_S | ContextVars are never read and task steps are cut at `Handle._run` (X64, X65). A sectioned consumer task that drains other gates' jobs is L-WHERE |
| R3-B3 hook swallows signal exceptions | CLOSED_S | The hook has no try/except (H2 with its mutant) |
| R3-D1 wraps family | CLOSED_S | (a) X49; (b) class-based wrappers refuse NOT_A_FUNCTION (X20); (c) X51; (d) the reverse over-block is gone (V13) |
| R3-D2 close checks skipped/ignored | CLOSED_S | No close-time refusals exist. Open-time refusals are recorded and refuse at score (X76–X80). A raised section keeps its counts (V25) |
| R3-D3 finalizer deadlock | CLOSED_S | The hook and `record()` take no lock; one RLock covers the rest (H1 with its mutant) |
| R3-D4 per-close gc cost | CLOSED_S | No gc at resolution or close; the gc scan at exit is refcount-gated (H5) |
| R3-D5 library daemon threads | CLOSED_S | Other threads are never credited, so there is no THREAD_OUTLIVES (V24) |
| R3-D6 same name in two shards; singledispatch | CLOSED_S | Openings are merged per name (V22); the dispatcher is minted and passes provenance through `__wrapped__` (V06) |
| R3 nit: SimpleNamespace | CLOSED_P | Own-dict instance steps (V08); INSTANCE_PATH names the class |
| R3 nit: PEP 562 | CLOSED_P | Fallback when the module defines `__getattr__` (V10). A lazy re-export refuses FOREIGN_DEFINITION with a message saying which module to declare |
| R3 nit: sticky hook_failed | CLOSED_S | No such flag; notes are per opening |
| R3 nit: Ctrl-C drops a chained profiler | CLOSED_S | Nothing is chained; a foreign profiler refuses at open and is left untouched |
| R3 nit: f_locals cost | CLOSED_S | `f_locals` is never read. The f_back walk cost is disclosed |
| R3 nit: closure clone with identical cells | CLOSED_S / LIMIT | Pre-trace and factory clones run other code (X48). In-trace clones of M_T with the same globals are L-CLONE |
| R3 nit: SECTION_CONTEXT stays set | N/A | No ContextVar exists |
| J1-X1 / all designs: stub bound before the trace | CLOSED_P | FOREIGN_DEFINITION by `__globals__` (X26–X30). An in-module stub or a wraps-stamped stub is L-STUB (R05, R06) |
| J1-X2 / J2: cross-thread job into a loop inside a section | CLOSED_S | `Handle._run` cut (X65), verified on 3.10–3.13. Non-asyncio loops are L-WHERE (R10) |
| J1-X4 / J2: queue drain, sectioned consumer | LIMIT | L-WHERE, pinned (R01, R02); a sectioned job on a sectioned consumer fails closed (X77) |
| J1: open-time refusals not recorded | CLOSED_P | Recorded into `problems` (X76, X78–X80, X32) |
| J2: PROFILER_LOST refusal is flaky | CLOSED_S | Demoted to a note. The verdict was PASS 20/20 on each version, with the note appearing 12–15 times out of 20 (H2, V26) |
| J2: SECTION_UNFINISHED over-blocks | CLOSED_S | Demoted; calls in raised openings count (V25) |
| J2: message says "never executed" misleadingly | CLOSED_P | New wording plus `dispatched`/`unattributed` counts and the fixed sentence (X72, X73, which check the message text) |
| J2: ALIAS over-block | CLOSED_S | Aliases are accepted and every name is credited (V02) |

---

## P1 retro under this spec

**Harness, unchanged.** `papers/first-afference/run_p1.py` is used unmodified. `styxx/power_QUARANTINED.py.txt` is loaded as `styxx.power`, and `run_p1` is loaded exactly as `run_protocol_v5d._load_p1` does it. `run_p1` binds `from styxx.power import ... reachable` before the trace, so the calls go through a captured alias.

**Declaration.** P1's G4 gets `exercises = [effective_n, order_stat_bar, false_positive_rate, min_detectable_bar, reachable]`, all under `styxx.power`.

**The only runner change:**
```python
deg = cov.run("G4_refuses_degenerate", run_p1.degenerate, np.random.default_rng(run_p1.SEED))
```

**Results.** Reproduced with the scratch prototype (`synth/s1_retro.py`) on 3.10.20, 3.11.15, 3.12.3 and 3.13.12, with identical output:

- **Resolution.** All five targets pass FOREIGN_DEFINITION: each function's `__globals__ is sys.modules["styxx.power"].__dict__`.
- **Metric.** `degenerate_refusal_rate` is 1.0.
- **Section record.** Exactly `[{'calls': {'styxx.power:reachable': 12}, 'ambiguous': {}, 'end': 'returned', 'notes': []}]`. `uncredited` is empty and `problems` is `[]`.
- **Verdict.** score() refuses with `[V5:NOT_EXERCISED] gate 'G4_refuses_degenerate': COVERAGE VIOLATION -- not executed on the stack of any opening of section 'G4_refuses_degenerate': ['styxx.power:effective_n', 'styxx.power:order_stat_bar', 'styxx.power:false_positive_rate', 'styxx.power:min_detectable_bar'] (did execute ['styxx.power:reachable'])`. It names exactly the four unexercised functions.
- **Cleanup.** `reachable.__code__` is restored and `sys.getprofile()` is None afterwards.

Minting is what makes the unmodified run work. The call site's pre-bound alias is the very function object whose `__code__` was minted, so name patching would have missed all 12 calls.

**Reported, not gated.** A G1 companion (`historical` under `exercises: [order_stat_bar]`) records `order_stat_bar: 1`, reached transitively through `reachable(n_draws>1)`. It passes, as the v5 prereg anticipated (R11).

---

## Over-blocking, disclosed

1. **Off-stack work never counts.** Nothing counts unless it runs on the section's own stack, above the dispatch cut. That excludes threads and grandchildren started in the section, thread pools, executors, `run_in_executor`, `asyncio.to_thread`, `multiprocessing.pool.ThreadPool`, library worker threads, asyncio child tasks (`create_task`, `gather`, TaskGroup, `ensure_future`, `shield`, `as_completed`, `wait_for` on ≤3.11) and loop callbacks. **Remedy:** each job opens its own section, with `cov.run` inside the submitted function or `run_async` inside the task. With `eager_task_factory` (3.12+), only a child's first synchronous step counts (X82).
2. **Event loops must run outside the section.** `cov.run(name, asyncio.run, main())`, or any loop run inside `cov.run`, counts nothing (X73). Use `asyncio.run(cov.run_async(name, main))`.
3. **Sections must be calls.** There is no `with` form, so fixtures and ExitStack cannot open sections. A generator or coroutine function passed to `run()` does its work after the close: the section gets a LAZY_RESULT note and reads NOT_EXERCISED.
4. **No same-tracer nesting on one stack** above the cut (NESTED_SECTION).
5. **A swallowed refusal refuses the whole trace.** Any swallowed open-time refusal (NESTED_SECTION, UNDECLARED_SECTION, TRACE_INACTIVE, FOREIGN_PROFILER, REENTRY), and any tripwire (CLONE_*, CODE_SWAPPED), refuses every declaring gate scored against that trace, including gates unrelated to it.
6. **Foreign profilers.** Any pre-existing `sys.setprofile` profiler on the opening thread refuses FOREIGN_PROFILER: pure-Python profilers on every version; cProfile, profile, yappi and pyinstrument on ≤3.11. A profiler started inside a section blinds the rest of that section on that thread (PROFILER_LOST note, then possibly NOT_EXERCISED). settrace tools such as coverage.py and pdb are unaffected. cProfile coexists on 3.12+.
7. **Hook loss.** Hitting the recursion limit, signal-handler exceptions (pytest-timeout's signal method), KeyboardInterrupt or a harness `setprofile` drops the hook. Calls after the drop on that thread go uncounted until that thread's next open. The verdict depends only on the calls made before the drop.
8. **Declarable objects are limited.** Declarable: FunctionType, staticmethod/classmethod of one, and C `lru_cache`/`cache` wrappers (through the body). Refused:
   - class-based wrappers, `partial`, `property`/`cached_property`, bound methods, `singledispatchmethod`;
   - builtins, C, Cython and numba callables; MagicMock;
   - attributes that come from a class through an instance; modules mid-path; inherited methods (declare the definer);
   - a cache wrapper whose body is also bound in the namespace (declare the body instead).
9. **FOREIGN_DEFINITION.** Refused: re-exports (declare the defining module); products of a no-`wraps` decorator or a factory defined in *another* module (remedy: add `functools.wraps` or declare a callee); attrs- and namedtuple-generated methods; functions generated by exec into private namespaces; autospec mocks and spies installed before the trace (pytest-mock `spy`), which should be installed inside the trace; PEP 562 lazy re-exports.
10. **A wrapped target is the wrapper.** Calling the inner function directly (`__wrapped__` or another reference) does not exercise it.
11. **Cache hits do not count.** A body cached before the section opened reads as unexercised.
12. **`T.__code__` is a different, equal object during the trace.** Code-identity tools such as line_profiler and code-keyed caches see the change. Hot reload of `__code__` refuses CODE_SWAPPED, and `importlib.reload` during the trace under-counts.
13. **A section open at trace exit** counts only the calls made before exit.
14. **Functions executed only inside profile or trace callbacks** can never be credited. That includes the styxx hook itself.
15. **Child processes are invisible.**
16. **v5c/v5d valid cases that v5e refuses:** `thread_started_in_section`, `thread_pool_inside_section`, `x2_grandchild_thread_in_section`, `asyncio_task_in_one_section` (loop inside the section) and `preexisting_python_profiler_chained`.
17. **Cost.** See Mechanism: the per-event hook, the per-hit f_back walk, and importing asyncio at the first enter.

---

## Stated limits

- **Carried forward.** Exercised is not tested: one call satisfies a declaration. Transitive calls count. Only declared gates are checked. The trace is written by the runner, so forgery is an accepted residual under an honest-but-careless threat model. Hardcoded values (P1's G3) are out of scope.
- **L-WHERE: attribution certifies where code ran, not who asked for it.** Work another gate supplies as data is credited to the section whose stack runs it. Examples:
  - queues drained inline, or by a consumer that opened its own opening of the section (judge 1's X4);
  - `concurrent.futures` done-callbacks that fire on the section's stack;
  - generators or coroutines created elsewhere and resumed there;
  - non-asyncio schedulers run inside a section: trio, curio, uvloop's Cython handles, Twisted, gevent, `sched`, hand-rolled trampolines;
  - eager tasks' first steps.

  A careless harness can reach this through a shared consumer, and it is pinned by R01, R02, R09 and R10.
- **L-RUNTIME: CPython-injected code counts for the section whose stack it lands on.** That covers signal handlers, `__del__` and weakref finalizers, gc callbacks, audit hooks and import-time module code (R08).
- **L-CLONE: the class-A residual.** During the trace, code reads M_T and then does one of three things: builds a function with T's own globals and drops it before exit; runs `exec(M_T, T.__globals__)`; or assigns `U.__code__ = M_T` and swaps it back before exit. Each of these is credited as T (R03, R04). A live clone is caught by CLONE_ALIVE, foreign globals by CLONE_CALLED, and a swap left in place by CODE_SWAPPED.
- **L-STUB.** Provenance proves where the code was defined, not that it is the original binding. A stub defined in the declared module, or a wraps-stamped stub bound before the trace, is credited (R05, R06).
- **L-CACHE.** A cache wrapper's target is its body. Direct calls of the body, through `__wrapped__` or a reference captured before decoration, count (R07).
- **L-BLIND.** A harness that saves the hook and reinstalls it later leaves a window with no note. This can only under-count.
- **L-ASYNC-EXC.** An asynchronous exception that lands between `_open`'s registration and `run`'s `try` leaves the opening "open" (OPEN_AT_EXIT). No credit can follow, because the anchor frame is dead.
- **Counts are frame entries.** Generator and coroutine resumptions count again (a two-yield generator records 3).
- **Re-entry through finalizers or signal handlers.** When one re-enters `_open`/`_close` on the same thread, the RLock serializes it. The worst case is lost counts plus a spurious note.
- **Interrupted exit.** It yields TRACE_INCOMPLETE and may leave minted code installed (equal code).
- **Diagnostic buckets are partial.** They see only threads that have an open opening at the time, and they are never evidence.
- **Scope of testing.** CPython only. 3.10–3.13 executed; 3.9 not executed; 3.14 unsupported until `Handle._run` and the frame model are re-validated. Free-threaded builds, greenlet and gevent are untested.

---

## Exam cases required

### Exam harness rules (frozen with the prereg before implementation)

**How cases run:**
- Each case runs in its own thread, inside the outer self-trace as `cov.run(<gate section>, case)`, with a 30 s join watchdog.
- The exceptions are signal cases and hazard sweeps. They run on the main thread, before the self-trace.

**How cases pass:**
- A violation passes only if the refusal message *starts with* its expected `[V5:CODE]`.
- A valid case passes only if it scores PASS with exactly the listed union counts, plus any listed notes and ends.
- A residual case passes only with its documented outcome.

**Leftover checks after every case:**
- `sys.getprofile()` is None on the case thread;
- `_THREADS`, `_ANCHORS`, `_MINTED` and `_BY_FN` are empty and `_ACTIVE == 0`;
- every fixture function's `__code__` is its original;
- `threading.getprofile()` is unchanged.

**Versions.** Everything must be identical on 3.10–3.13, except the version-keyed cases (X81, V33, X82).

### Violation cases (expected code)

| id | shape | code |
|---|---|---|
| X01–X05 | `exercises` is `[]`; a str; has a trailing `\n`; has a non-ASCII name; has a duplicate | DECL |
| X06, X07 | `section` without `exercises`; `section: 5` | SECTION_DECL |
| X08 | prereg declaring nothing | NOTHING_DECLARED |
| X10, X11 | module raising RuntimeError at import; module with a SyntaxError | UNRESOLVED |
| X12, X13 | name absent, no `__getattr__`; module `__getattr__` raising | UNRESOLVED |
| X14 | `Sub.fit`, inherited | INHERITED |
| X15, X16, X17 | `default_model.fit`; `pkg:sub.fn`; a step through a `__slots__` object | INSTANCE_PATH |
| X18–X22 | partial; property; class-based update_wrapper instance (T01b); builtin; bound-method alias | NOT_A_FUNCTION |
| X23 | `mock.patch("m.f")` (MagicMock) before the trace | NOT_A_FUNCTION |
| X24, X25 | `lru_cache(None)(abs)`; `fast = lru_cache(None)(_impl)` with `_impl` bound | NOT_A_FUNCTION |
| X26 | stub from another module bound before the trace (J1-X1) | FOREIGN_DEFINITION |
| X27 | `mock.patch(autospec=True)` before the trace | FOREIGN_DEFINITION |
| X28 | product of a no-wraps decorator from another module | FOREIGN_DEFINITION |
| X29 | re-export declared as `b:f` | FOREIGN_DEFINITION |
| X30 | function exec'd in `{"__name__": module}` (a `__module__` check would pass it) | FOREIGN_DEFINITION |
| X31 | nested tracer entered after the outer tracer's `T.__code__` was swapped | CODE_SWAPPED |
| X32 | tracer entered twice, second entry swallowed; then score | REENTRY (raised and at score) |
| X33 | one good target plus one unresolvable target; also asserts the good target's `__code__` is untouched | UNRESOLVED |
| X40 | factory sibling: declare `check_low`, call `check_high` | NOT_EXERCISED |
| X41 | no-wraps sibling: declare `entry_a`, call `entry_b` | NOT_EXERCISED |
| X42 | `timed(cheap_path)()` at runtime; `score_all` declared (R2-B1) | NOT_EXERCISED |
| X43, X44 | `make_mul(3)(5)` for `double`; same cells with another default (R3-B1) | NOT_EXERCISED |
| X45, X46, X47 | vendored equal copy; exec'd module copy; `DB()` for `DA.__init__` | NOT_EXERCISED |
| X48 | same-globals clone made before the trace, called | NOT_EXERCISED |
| X49, X50, X51 | plain caller of the wraps inner (T01a); `run_safe` for `run_fast`; per-call wraps sibling (T01c) | NOT_EXERCISED |
| X52 | `wrapped_entry.__wrapped__(x)` | NOT_EXERCISED |
| X53 | name rebound to a local stub during the trace | NOT_EXERCISED |
| X54 | cache hit only (body cached before the section) | NOT_EXERCISED |
| X55, X56 | `FunctionType(T.__code__, {})()`; `exec(T.__code__, {})` | CLONE_CALLED |
| X57 | same-globals in-trace clone kept alive | CLONE_ALIVE |
| X58 | `U.__code__ = T.__code__`, U kept and called | CLONE_ALIVE |
| X59 | T called, then `T.__code__` reassigned | CODE_SWAPPED |
| X60, X61 | thread started in A calls while B is open; unsectioned thread calls during B | NOT_EXERCISED (both gates) |
| X62 | task created in `run_async` A, awaited in B | NOT_EXERCISED |
| X63 | pool shared by concurrently open A and B; B's unsectioned job (R2-B2) | NOT_EXERCISED for A |
| X64 | A's lazily started consumer tasks run B's job (R3-B2, t12) | NOT_EXERCISED for A |
| X65 | `run_coroutine_threadsafe` and `call_soon_threadsafe` into a loop inside `cov.run(A)` (J1-X2) | NOT_EXERCISED for A |
| X66, X67 | thread calls after close; task created in G, awaited after G closed (R06) | NOT_EXERCISED |
| X68, X69 | grandchild thread after close; generator from G resumed after close, unsectioned | NOT_EXERCISED |
| X70 | coroutine opening A resumed inside B; f runs only after the resume (`ambiguous` = 1 on both) | NOT_EXERCISED for A |
| X71 | only call made after tracer exit, in a still-open section (OPEN_AT_EXIT) | NOT_EXERCISED |
| X72 | gather children inside `run_async`; message contains `dispatched` and the fixed sentence | NOT_EXERCISED |
| X73 | `cov.run(G, asyncio.run, main())` | NOT_EXERCISED |
| X74 | `run(G, async_fn)`; message contains LAZY_RESULT | NOT_EXERCISED |
| X75 | harness `sys.setprofile(None)` before the target; message contains PROFILER_LOST | NOT_EXERCISED |
| X76 | same-tracer nested open, swallowed; an unrelated gate also refuses | NESTED_SECTION |
| X77 | sectioned job on a sectioned consumer (judge 1's X4b) | NESTED_SECTION |
| X78 | undeclared section name, swallowed | UNDECLARED_SECTION |
| X79 | `run` after exit, swallowed; record taken afterwards | TRACE_INACTIVE |
| X80 | pure-Python profiler present at open, swallowed; profiler still installed | FOREIGN_PROFILER |
| X81 (≤3.11 only) | cProfile enabled before open; `Profile` still installed | FOREIGN_PROFILER |
| X82 (≥3.12 only) | eager task: f before the first await, g after; `{f:1}` recorded | NOT_EXERCISED (g) |
| X90, X91 | `record()` inside the trace; `record()` before enter | TRACE_ACTIVE |
| X92 | fault injected into the exit checks, then `record()` | TRACE_INCOMPLETE |
| X93, X94 | trace missing; result not a dict | NO_TRACE |
| X95 | a committed v5d `/1` trace | WRONG_TRACER |
| X96–X108 | extra top-level key; int key in targets; non-str target value; None key in sections; section as a dict (v5d shape); section `[]`; opening missing `notes`; `end: "finished"`; unknown note code; unknown problem code; `problems` not a list; `uncredited` missing a key; int key in calls | BAD_TRACE |
| X109 | trace from another gates block | STALE_TRACE |
| X110 | target subset | TARGET_SET |
| X111–X115 | count `True`; count `0`; undeclared key in calls; in ambiguous; in uncredited | BAD_COUNT |
| X116 | gate's section never opened | SECTION_ABSENT |
| X117 | `check_metrics(None / [] / 's' / 5)` returns `usable: False` without raising (exam sentinel REPORTED) | REPORTED |
| X118 | P1 retro (G2): exactly `{reachable: 12}`, the other four named | NOT_EXERCISED |

### Valid cases (expected union counts)

| id | shape | counts / property |
|---|---|---|
| V01 | plain `f` | `{f:1}` |
| V02 | `f` and `alias_f` declared, `f` called once | `{f:1, alias_f:1}` |
| V03, V04 | `double(5)`; `entry_a(1)` | `{double:1}`; `{entry_a:1}` |
| V05, V06 | `DA()`; `dispatch(1)` | `{DA.__init__:1}`; `{dispatch:1}` |
| V07 | `cached.cache_clear()`, then `cached(1)` twice | `{cached:1}` |
| V08, V09, V10 | `NS.handler()`; `Base.fit` via `Sub()`; PEP 562 `lazy_fn` defined in the module | 1 each |
| V11 | wraps wrapper from another module | `{wrapped_entry:1}` |
| V12, V13 | staticmethod + classmethod; T01d `score` via `score_v1` | 1 each; `{score:1}` |
| V14 | generator with two yields, consumed | `{gen:3}` |
| V15 | nested tracers on the same target | outer `{f:1}`, inner `{f:1}`; code restored after both |
| V16 | two tracers exited non-LIFO | both exact; code restored; registries empty |
| V17 | two tracers in two threads, same target, interleaved | `{f:3}` and `{f:5}` |
| V18 | `asyncio.run(cov.run_async(G, main))` | `{f:1, g:1}` |
| V19 | tasks in a loop inside `cov.run(A)`, each in `run_async(B)` | A `{f:1}`, B `{g:2}` (pins the cut in the NESTED walk) |
| V20 | 5 gathered `run_async` openings | `{g:5}` |
| V21 | `to_thread(cov.run, G, f)` plus 8 ThreadPoolExecutor `cov.run` jobs | `{f:9}`; no hooked threads left |
| V22 | two threads shard section G concurrently | sum of both |
| V23 | multiprocessing ThreadPool jobs using `cov.run`, terminate without join | `{f:4}` |
| V24 | daemon thread started in the section outlives it | `{f:1}` |
| V25 | three per-case sections that raise, caught by the harness | `{f:3, g:3}`; ends `raised` |
| V26 | `setprofile(None)` after the target | `{f:1}`; PROFILER_LOST note |
| V27 | RecursionError caught after the target | `{f:1}` |
| V28 | coroutine section closed on another thread | `{f:1}`; THREAD_HOP note |
| V29 | section still open at exit, target called before exit | `{f:1}`; end `open`; OPEN_AT_EXIT |
| V30 | blind window: A drops the hook and B reinstalls it on the same thread | A `{f:1}` with PROFILER_LOST (pins the epoch); B `{g:1}` |
| V31 | harness reinstalls a saved hook outside sections | `sys.getprofile()` is None after one event |
| V32 | stress: 8 threads, 40 tasks, unsectioned noise; 3 runs | recorded equals expected; 0 cross-credit; no leftovers |
| V33 (≥3.12 only) | cProfile enabled before open | `{f:1}` |
| V34 | the exam's own self-coverage | every declared machinery target ≥ 1; `run` exactly equals the number of inner runs |

### Documented residuals (pinned outcome)
- **R01** (J1-X4): A's sectioned consumer drains B's job. Outcome: A PASS `{f:1}`.
- **R02**: A inline-drains B's queued job. Outcome: A PASS.
- **R03**: an in-trace same-globals clone is called and dropped. Outcome: PASS.
- **R04**: `exec(T.__code__, T.__globals__)`. Outcome: PASS.
- **R05**: a stub defined in the declared module is bound before the trace. Outcome: PASS.
- **R06**: `functools.wraps(real)(fake)` from another module is bound before the trace. Outcome: PASS.
- **R07**: a cache body is called through `__wrapped__`. Outcome: PASS.
- **R08**: a cyclic finalizer of B's object is collected on A's stack. Outcome: A PASS.
- **R09**: a generator created in B is resumed in A. Outcome: credited to A.
- **R10**: a `sched`/trampoline scheduler inside A runs B's jobs. Outcome: A PASS.
- **R11**: the P1 G1 companion. Outcome: `order_stat_bar:1`.

A residual whose outcome changes is a spec change and needs a new prereg.

### Hazard sweeps, each paired with a detection mutant
- **H1.** Cyclic garbage whose `__del__` calls a target. Sweep gen-0 thresholds 1–40 at `_open`, `_close`, `record`, the hook and `__exit__`, with a 10 s watchdog. Expect no hang. **Mutant:** the hook takes a non-reentrant Lock, and the sweep must detect at least one hang.
- **H2.** A SIGALRM `Timeout(Exception)` in a tight traced loop, after a target call, 20 trials. Expect 20/20 propagated and 20/20 PASS; the note is not asserted. **Mutant:** the hook is wrapped in `except Exception`, and propagation must drop below 20/20.
- **H3.** KeyboardInterrupt raised from a signal, 5/5. Expect it to propagate and leave no hook behind.
- **H4.** Performance (reported, not gated): one close on a 1M-object heap takes under 1 ms, and there is no gc at resolution.

### Mutation audit
Each rule has a mutant, and the exam fails that mutant in the cases named:

| rule deleted or weakened | cases that fail |
|---|---|
| minting (observe the original code) | X40–X44 |
| `is` replaced by `==` | X45, X46 |
| `f_globals` check | X55, X56 |
| CLONE_ALIVE | X57, X58 |
| CODE_SWAPPED at exit / at entry | X59 / X31 |
| unwrap reintroduced | X49, X50 |
| FOREIGN_DEFINITION / based on `__module__` / without the `__wrapped__` chain | X26–X29 / X30 / V11, V06 |
| resolve-all-before-mint | X33 |
| INHERITED / own-dict instance steps | X14 / X15, V08 |
| PEP 562 fallback / cache body / alias acceptance | V10 / V07, X25 / V02 |
| dispatch cut in attribution / in the NESTED walk | X65 / V19 |
| exactly-one-opening-per-tracer | X70 |
| emptying `_by_code` at exit | X71 |
| recording open-time refusals | X76, X78–X80, X32 |
| score reads `problems` | X55–X59 |
| notes promoted back to refusals | V25–V30 |
| union over openings | V21, V22 |
| epoch | V30 |
| self-removal / last-close removal | V31 / leftover checks |
| TRACE_ACTIVE / TRACE_INCOMPLETE | X90 / X92 |
| each BAD_TRACE and BAD_COUNT clause | X96–X115 |
| LAZY_RESULT | X74 |
| no try/except in the hook / no lock in the hook | H2 / H1 |

### Process gates
Carried from v5d:

- **G_EXAM_FROZEN**: the runner sha256 is frozen in the v5e prereg before any implementation.
- **G0**: violations refused with their own code = 1.0. It declares `styxx.protocol:Experiment._check_coverage`, `_resolve_target`, `_CoverageTracer._open` and `_CoverageTracer.__exit__`.
- **G1**: valid cases exact = 1.0.
- **G2**: the P1 retro is exact (X118).
- **G3**: no v4/v5 disagreement over the pairable committed results.
- **G4**: population ≥ 33.

Added:

- **G5**: residual outcomes as documented = 1.0.
- **Mutation audit**: every mutant in the table fails at least one case. A round-4 red team runs this before any shipping claim.