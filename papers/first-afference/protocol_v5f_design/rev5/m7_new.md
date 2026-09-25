### M7. `_open`, `_commit`, `_run`, `_run_async`, `_detach` (no mutex)
The open checks are listed under Attribution. The rest (revision 5; runnable in `rev5/spec_rev5_eventpath.py`, which checks this text on 3.12.3 and 3.13.12):
```python
def _run(core, section, fn, args, kwargs):      # module level: its frame is the anchor, its locals hold no facade
    o = _open(core, section, sys._getframe())   # checks and append only (At open, steps 1-6)
    if o is None: return fn(*args, **kwargs)    # forked child: pass-through
    end = "raised"
    try:
        _commit(o)                              # revision 3: inside the try
        result = fn(*args, **kwargs); end = "returned"
    finally:
        _detach(o, (end, ()))                   # no loop in the try body, nor in any function it calls
        o.frame = None                          # revision 4 (B1): the opening's own finally releases the anchor frame
    t = type(result)                            # `is` chain, never `in` (see Resolution)
    if t is GeneratorType or t is CoroutineType or t is AsyncGeneratorType: o.lazy = _lazy_text(result)
    return result

def _commit(o):                                 # At open, steps 7-8 (revision 5 order)
    _ANCHORS[o.frame] = o                       # the store; o.frame is set: only this opening's finally releases it
    if 'fin' in o.fin or 'exiting' in o.core.marks:   # step 8: a detacher claimed o, or exit began
        _detach(o, ("open", (OPEN_AT_EXIT_TEXT,)))
        o.core.problems.append(TRACE_INACTIVE_TEXT)
        raise GateSpecError(TRACE_INACTIVE_TEXT)
    _unwind_on(o)                               # one call, after the store: no clear can follow while o is registered
    o.armed = True                              # last: the body may run now

def _unwind_on(o):
    # ONE CALL { if get_tool(t) is _TOOL_NAME and _ANCHORS.get(o.frame) is o:
    #                if not (get_events(t) & PY_UNWIND):
    #                    for p in _ANCHORS.values(): if p.armed: p.core.flags['UNWIND_LOST'] = True
    #                set_events(t, PY_UNWIND) }
    t = _TOOL[0]; get_tool, get_events, set_events = _MON[0][0], _MON[0][1], _MON[0][2]
    _CONSUME(_chain(
        _map(_setitem, _map(_FLAGS, _filter(_ARMED, _chain.from_iterable(_map(_VALUES,
            _compress(_compress(_compress((_ANCHORS,), _map(_is, _map(get_tool, (t,)), _NAME1)),
                                _map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))),
                      _map(_not, _map(_and, _map(get_events, (t,)), _PYU1))))))), _LOST_KEY, _TRUE),
        _map(set_events,
             _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),
                       _map(_is, _map(_ANCHORS.get, (o.frame,)), (o,))),
             _PYU1)))

def _unwind_off(key):                           # _detach (key = the anchor frame), and last in every reconciliation (None)
    # ONE CALL { _ANCHORS.pop(key, None); if get_tool(t) is _TOOL_NAME and not _ANCHORS: set_events(t, 0) }
    t = _TOOL[0]; get_tool, set_events = _MON[0][0], _MON[0][2]
    _CONSUME(_chain(_map(_ANCHORS.pop, (key,), _NONE1),
                    _map(set_events, _compress(_compress((t,), _map(_is, _map(get_tool, (t,)), _NAME1)),
                                               _map(_not, (_ANCHORS,))), _ZERO1)))

def _detach(o, fin):
    o.fin.setdefault("fin", fin)                # one claim: first finaliser wins
    fr = o.frame                                # never assigned here: every detacher pops by the anchor's own key
    if fr is not None:
        if o.armed and not (_MON[0][1](_TOOL[0]) & PY_UNWIND) and _ANCHORS.get(fr) is o:
            o.core.flags['UNWIND_LOST'] = True  # the event first, the anchor last: an outside party cleared it
        _unwind_off(fr)                         # one call: pop, then clear iff no anchor is left

def _take(t):                                   # M3 step 0 and _ensure_tool
    # ONE CALL { if get_tool(t) is None: use_tool_id(t, _TOOL_NAME) }; the caller then tests _named(t)
    _CONSUME(_map(_MON[0][5], _compress((t,), _map(_is, _map(_MON[0][0], (t,)), _NONE1)), _NAME1))

def _register(t):                               # _ensure_tool, M3 step 0, M5 X5
    # ONE CALL { if get_tool(t) is _TOOL_NAME: register our five callbacks }; returns the previous ones ([] if not named)
    return list(_map(_MON[0][4], _chain.from_iterable(_map(_repeat, _compress((t,), _map(_is, _map(_MON[0][0], (t,)), _NAME1)), (5,))),
                     _EVENTS5, _CALLBACKS5))

def _set_local(t, code, events):                # Minting step 4, _retire step 2
    # ONE CALL { if get_tool(t) is _TOOL_NAME: set_local_events(t, code, events) }
    _CONSUME(_map(_MON[0][3], _compress((t,), _map(_is, _map(_MON[0][0], (t,)), _NAME1)), (code,), (events,)))

def _named(i): return _MON[0][0](i) is _TOOL_NAME          # revision 5: identity, so no __eq__ of any kind runs

def _ours(): return _TOOL[0] is not None and _named(_TOOL[0])
```
M1 also binds `_repeat = itertools.repeat`, `_EVENTS5 = (PY_START, PY_RESUME, PY_RETURN, PY_YIELD, PY_UNWIND)` and `_CALLBACKS5 = (_on_entry, _on_entry, _on_exit, _on_exit, _on_unwind)`. styxx's global event set is only ever PY_UNWIND or nothing. `set_events`, `set_local_events`, `register_callback` and `use_tool_id` are called only inside one-call steps, except `_forget_in_child` in the single-threaded child (G_HYG). Every test of a name goes through `_named` or a one-call step's `_is` gate (G_HYG).

**One-call steps (revision 5).** A *one-call step* is one statement that builds a lazy pipeline and hands it to one consuming builtin, `_CONSUME` or `list`. The pipeline is made of `map`, `filter`, `itertools.chain`/`compress`/`repeat`, and `operator` callables. It calls only C callables: `operator` functions, `dict.get`, `dict.pop` and `dict.values`, `attrgetter` on `__slots__` fields, and the `sys.monitoring` functions in `_MON`. Building the pipeline reads no shared state. The statement reads only `_TOOL[0]` and `o.frame`, which only the mutex and the opening's own thread change. Every read and every write happens inside the one consuming call, in C. CPython runs no Python code inside a C call that makes no Python-level call: no eval-breaker check runs there. So no thread switch, signal handler, cyclic-gc finalizer (3.12 and later run gc only at eval-breaker checks) or asynchronous exception lands there, and no greenlet switch. No trace or profile function and no sys.monitoring callback fires for calls made from C, and none of these calls raises an audit event. The whole step is therefore atomic with respect to everything else in the process, instruments included. `rev5/t1_onecall_atomic.py` shows this on 3.12.3 and 3.13.12:
- *Per-event sweeps.* One trial per event that an INSTRUCTION tool, a CALL + C_RETURN tool, a BRANCH tool, a pure-Python `sys.setprofile` function and opcode tracing deliver inside the clearing function. Each trial registers an anchor at that event. The one-call step never clears after an anchor registered while the event was set: 0 violations in 48 / 32 / 0 / 3 / 48 trials per version. The two-statement control (`A.pop(key)`, then `if not A: set_events(t, 0)`) violates under every one of the five, in 5–6 / 1 / 1 / 1 / 5–6 trials.
- *What instruments see.* During a one-call step, a profile function sees one `c_call`, the consumer's, and a CALL tool sees only the pipeline's constructors. Neither sees `get_tool`, `get_events`, `set_events` or `pop`.
- *Audit events.* None, from any one-call step.
- *Gc and signals.* A cyclic-gc finalizer and a 20 µs SIGALRM handler, each registering an anchor at threshold 1: 0 violations in about 4,600 closes and 27,000 interrupts per version.
- *Threads.* A pure-Python profiler that yields the GIL at every C call in the close path, over 4 threads: 0 of about 71,000 body samples found the event clear. The two-statement control found it clear in 165 and 195.

G_HYG checks the shape: each of the seven functions above that holds a one-call step (the three `_unwind_*`/`_detach` steps' `_unwind_on`, `_unwind_off`, and `_take`, `_register`, `_set_local`) is exactly that statement, and its pipeline names only the M1 one-call names, `_MON`'s functions, `_ANCHORS.get`, `_ANCHORS.pop` and literal tuples.

`_run_async` has the same shape, with `_commit(o)` and then `result = await afn(*args, **kwargs)` as its try body, and the same two statements in its `finally`. That `await` compiles to a SEND loop. Its throw-then-return path is taken when a thrown exception is handled by the awaited object, which then returns. On that path, the closing jump after CLEANUP_THROW lies outside the try's exception-table range on 3.12.3 and 3.13.12. On 3.12 it is a JUMP_BACKWARD, which checks the eval breaker, so a signal landing there skips the `finally` (`rev1/p19_run_async_throw_path.py`). On 3.13 it is JUMP_BACKWARD_NO_INTERRUPT, which only an injected fault reaches. No count, note, refusal or termination depends on that `finally`. The opening's anchor frame is dead, so it is on no live chain, and exit's X3 or a prune finalises the opening as `('open', OPEN_AT_EXIT)`, inside I6. Until then the dead anchor keeps PY_UNWIND set, which is L-DELIVERY scope only (U4 below), and the opening keeps its dead anchor frame (M1). `_run`'s try body, `_commit(o)` and the call, has no loop. Revision 5 has no loop in any function that `_run`'s try body or `finally` calls: the one-call steps iterate in C, not at a bytecode back-edge. Revision 4's `_await_clearers` loop is gone. `rev5/spec_rev5_eventpath.py` finds no backward jump in `_run`, `_commit`, `_unwind_on`, `_unwind_off`, `_detach`, `_take`, `_register`, `_set_local` or `_named`. It then faults every instruction of `_commit` and `_unwind_on`. In every trial `_run`'s `finally` ran and left no anchor and no event (24 and 113–117 trials per version). No signal position skipped `_run`'s `finally` (p10).

**The unwind scope (revision 2, M4; restated in revision 3; made atomic in revision 5).** The global PY_UNWIND is set only while some anchor is registered in this copy, so only while some section is open anywhere in the process. Revision 1 set it while any mint existed, which included a whole trace, zombies, and a freed id after exit. The protocol has no lock and no wait:
- the opener, inside `_run`'s `try`, stores its anchor, re-tests its claim (step 8), then runs `_unwind_on(o)`: one call that sets the event iff the id is named and o's anchor is still registered. Then it arms;
- every clear is `_unwind_off(key)`: one call that pops the key and clears iff the id is named and no anchor is left. The closer and every other detacher call it with the anchor frame, and the reconciliation calls it last with None.

*Why no clear can land under a registered anchor.* A machinery clear happens only inside an `_unwind_off` call, and only if that same call finds `_ANCHORS` empty. Nothing runs inside that call. So at the instant of any machinery clear, no anchor is registered. An opener O stores its anchor before its `_unwind_on`. From O's `_unwind_on` until O's pop, S is set, unless a party outside the machinery changes it. The argument uses no order between threads, no liveness test and no wait. It holds whatever Python code runs between two machinery steps, on any thread, O's own included. That covers a signal handler or finalizer that opens a section, a profiler, a CALL or INSTRUCTION tool, a greenlet switch, and a `run_async` section left suspended and resumed elsewhere. Revision 4's two exclusions for code on O's own thread (R19) and for greenlet switches are therefore gone. Revision 3 relied on `_ANCHORS or set_events(_TOOL[0], 0)` having no eval-breaker check between the test and the call. That fails under any tool that runs Python code at an instruction inside the expression, including tools this spec says coexist (the fourth critic's MF1; `critic4/a1_what_splits_test_and_clear.py`):
- a `sys.setprofile` or `threading.setprofile_all_threads` function (V48's shape), and cProfile with a Python timer;
- a sys.monitoring CALL callback, local or global;
- a sys.monitoring INSTRUCTION callback, the id-5 injector included, and a settrace function with `f_trace_opcodes` set;
- a BRANCH callback on 3.12.3 (not on 3.13.12).

Revision 4 tolerated them by making the opener wait for announced clearers. The wait closed cycles through user code and through sections opened inside a clearer's window (the fifth critic's MF1), and its same-thread exclusion lost calls silently (MF2). A one-call step is not split by any of these tools (`rev5/t1_onecall_atomic.py`), so revision 5 needs neither the announcement nor the wait.

*The invariant, with its windows.* Write S for "styxx's id has PY_UNWIND set" and A for "some anchor is registered".
- **U1. An armed section's body never runs with S clear while its core is crediting and alive.** This holds on every interleaving, fault-free or not, whatever Python code runs between two machinery steps, on any thread, this one included. The one exclusion is closed: a party outside the machinery that clears S, frees styxx's id, or changes its callbacks or local events (L-MONITOR). The body starts after the opener's `_unwind_on`, and by the argument above no machinery clear lands while its anchor is registered. The anchor stays registered until its own close, or until a detacher pops it: exit's X3 after the credit stop, or a reconciliation's prune of a dead core. After X3 nothing counts. After a prune the core is dead, and its record is never read again (M3). A fault in the machinery never clears S: faults only cut a step sequence short, and a fault cannot land inside a one-call step.
- **U2. A clear S with A set lasts only while an opener is between its anchor store and its `_unwind_on`,** on the opener's own thread, before its body starts, or after an outside party cleared S.
- **U3. A set S with no anchor never exists**, fault-free or after a fault, except after an outside party set S or freed styxx's id. Then it lasts until the next reconciliation's `_unwind_off(None)` or the next close that leaves no anchor. S is set only by `_unwind_on`, in the same call as a test that o's anchor is registered. A becomes empty only by a pop inside `_unwind_off`, in the same call as the clear. Revision 4 had two windows here: a detacher between its pop and its clear, and an opener whose anchor X3 popped after step 8, which set S and kept it for its whole uncredited body. Both are gone. `rev5/m5_modelcheck.py` checks this as STALE in every state of every configuration.
- **U4. After faults**, S set with no live section lasts only while a *dead anchor* stays registered. That follows a fault in a close before its `_unwind_off` call (at `_detach`'s first instructions, or while `_unwind_off` builds its pipeline), or a `_run_async` `finally` skipped by #130279 on 3.12. It lasts until the owning trace's exit detaches it at X3, or a reconciliation prunes it once its core is dead (revision 4: this also reaches a core that already exited, X146d). This is L-DELIVERY scope only. The dead anchor's frame is on no live chain, so no count, note or refusal depends on it. Revision 4's other fault window, a fault between a pop and its clear, no longer exists. In `rev5/spec_rev5_eventpath.py`'s fault sweep, every trial in the close path left either nothing or a dead anchor with S set, never S set with no anchor.

  A fault anywhere in `_commit`, which is revision 2's MF2 case, leaves neither: the `finally` pops the anchor (`o.frame` is still set) and clears S if no anchor is left.
- **What is lost (MONITOR_LOST completeness, revision 5).** Nothing is lost through the machinery, on any interleaving, fault-free or not (U1). A call lost through an outside party is noted in one of three places:
  - the section's close, or exit's X3, finds S clear under its armed, registered anchor;
  - the next `_unwind_on` anywhere in the process finds S clear, and notes every armed, registered opening in the same call in which it sets S;
  - the exit's MONITOR_LOST test finds the id freed and re-taken (`_LOST`) or taken by another tool.

  The one silent shape: the outside party that cleared S sets it again itself before any machinery step reads it. The notes are precise too. Every flag follows a state in which S was clear under an armed, registered anchor, which by U1 only an outside party can cause. `rev5/m5_modelcheck.py` checks both halves as LOSTNOTE and FALSEFLAG. Revision 4's close-time test alone was erased by any section that opened before the blinded close (the fifth critic's MF2; `critic5/c7_external_clear_masked.py`, X137d).

*Evidence (revision 5).*
- `rev5/t1_onecall_atomic.py`: above.
- `rev5/m5_modelcheck.py`: @@M5EVIDENCE@@
- `rev5/w5_witnesses.py`: every revision-5 witness passes under the spec and fails under its single-rule mutant, on both versions. The critic's shapes re-run clean:
  - R19's shape at every point of a close: `{t:1}`, no note. The loss appears only under a split `_unwind_off`;
  - the user-lock shape (c3): the open returns in 0.0 s;
  - sections opened inside two closes at once (c8): both return at once.
- `rev5/spec_rev5_eventpath.py`: above.

