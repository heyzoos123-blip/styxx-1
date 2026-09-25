# Exhaustive interleaving check of the section-scoped PY_UNWIND protocol (MF1, MF2, MF7), revision 2 against
# revision 3. An abstract model: the state is S (the global PY_UNWIND is set) and A (the registered anchors). Each
# thread is a list of atomic steps. A step boundary is placed wherever CPython 3.12/3.13 can switch threads or
# deliver an asynchronous exception: after every C call (get_tool, get_events, set_events, dict.pop/get) and at
# a Python call's RESUME. Revision 3's `if _ANCHORS: return` + `set_events(tool, 0)` is one step, because only
# loads lie between them (q1_test_then_call_atomic.py). The variant 'rev3-split' splits it, which is what an
# instrument that runs Python code at every instruction of the machinery (the id-5 injector) does.
#
# Threads: openers P1 and P2, each running one whole section (open, commit, a hit in the body, close), and a
# retirer R running `_retire` step 6 (rev 2: its own test-then-clear; rev 3: `_unwind_off()`). Every interleaving
# is explored (DFS over the reachable states), with 0, 1 or 2 injected faults. A fault lands at a step boundary
# of one thread: in rev 3, inside _run's try body (commit or body) it jumps to the finally (_detach); inside the
# finally it abandons the rest; in rev 2 the open steps are outside the try, so a fault there abandons the section
# and, after the commit, leaves a dead anchor.
# Properties:
#   U1   no hit runs with S clear: an open section always has the event set while its body runs;
#   A0   no state has a live anchor and S clear unless the owning opener is between its commit and its second
#        _unwind_on (before its body starts);
#   S0   no state has S set and no anchor unless some thread is inside its own window (an opener between its first
#        set and its commit; a closer between its pop and the end of its _unwind_off; R inside step 6);
#   END  when every thread has finished: S set with no anchor (stale), before and after one repair (_unwind_off, as
#        run by the next close or the next transaction's reconciliation); dead anchors counted separately;
#   FLAG a close that sets UNWIND_LOST (MONITOR_LOST at exit).
import sys, itertools

def opener_rev3():
    # pc: 0 append (outside try) | try: 1 on1 read, 2 on1 set, 3 commit, 4 on2 read, 5 on2 set, 55 o.armed = True,
    # 6 hit | finally: 7 claim + read o.armed, 8 read S and flag, 9 pop, 10 off read S, 11 off test+clear,
    # 12 off re-check
    return dict(n=13, try_=(1, 2, 3, 4, 5, 55, 6), fin=7, hit=6, commit=3,
                own_S=(3, 10, 11, 12, 110), own_A=(4, 5, 55), recheck=(12,), R_recheck=(2,))

def opener_rev2():
    # 0 append, 1 on1 read, 2 on1 set, 3 commit, 4 on2 read, 5 on2 set (all outside try) | try: 6 hit |
    # finally: 7 claim, 8 read S and flag (no anchor-identity guard), 9 pop, 10 off test A, 11 off read S,
    # 12 off clear, 13 off re-check
    return dict(n=14, try_=range(6, 7), fin=7, hit=6, commit=3,
                own_S=(3, 10, 11, 12, 13), own_A=(4, 5), recheck=(13,), R_recheck=())

def step_opener(rev, i, pc, loc, S, A, flags, split):
    """Execute step pc of opener i. Returns (next_pc, loc, S, A, flags, event) with next_pc None when done."""
    ev = None
    if rev == 3:
        if pc == 0: return 1, loc, S, A, flags, ev
        if pc in (1, 4): return pc + 1, S, S, A, flags, ev                      # get_events
        if pc in (2, 5): return (3 if pc == 2 else 55), None, (S or not loc), A, flags, ev
        if pc == 3: return 4, loc, S, A | {i}, flags, ev
        if pc == 55: return 6, loc, S, A, flags | {('armed', i)}, ev            # _commit's last statement
        if pc == 6: return 7, loc, S, A, flags, ('hit', S)
        if pc == 7: return 8, (('armed', i) in flags), S, A, flags, ev          # o.armed
        if pc == 8:
            if loc and not S: flags = flags | {('UNWIND_LOST', i)}
            return 9, None, S, A, flags, ev
        if pc == 9: return 10, None, S, A - {i}, flags, ev
        if pc == 10: return (11 if S else None), None, S, A, flags, ev          # off: read S; not set -> return
        if pc == 11:
            if split:                                                           # 'rev3-split': test, then clear
                return (None if A else 110), None, S, A, flags, ev
            return (None if A else 12), None, (S if A else False), A, flags, ev
        if pc == 110: return 12, None, False, A, flags, ev
        if pc == 12: return None, None, (True if A else S), A, flags, ev
    else:
        if pc == 0: return 1, loc, S, A, flags, ev
        if pc in (1, 4): return pc + 1, S, S, A, flags, ev
        if pc in (2, 5): return pc + 1, None, (S or not loc), A, flags, ev
        if pc == 3: return 4, loc, S, A | {i}, flags, ev
        if pc == 6: return 7, loc, S, A, flags, ('hit', S)
        if pc == 7: return 8, None, S, A, flags, ev
        if pc == 8:
            if not S: flags = flags | {('UNWIND_LOST', i)}
            return 9, None, S, A, flags, ev
        if pc == 9: return 10, None, S, A - {i}, flags, ev
        if pc == 10: return (None if A else 11), None, S, A, flags, ev          # test A, then get_tool (switch)
        if pc == 11: return (12 if S else None), None, S, A, flags, ev          # get_events
        if pc == 12: return 13, None, False, A, flags, ev                       # clear
        if pc == 13: return None, None, (True if A else S), A, flags, ev        # re-check
    raise AssertionError((rev, pc))

def step_retirer(rev, pc, loc, S, A, split):
    if rev == 3:                                                                # _unwind_off()
        if pc == 0: return (1 if S else None), S, A
        if pc == 1:
            if split: return (None if A else 10), S, A
            return (None if A else 2), (S if A else False), A
        if pc == 10: return 2, False, A
        if pc == 2: return None, (True if A else S), A
    else:                                                                       # "if _ANCHORS is empty and ours: clear"
        if pc == 0: return (None if A else 1), S, A                             # test A, then get_tool (switch)
        if pc == 1: return None, False, A
    raise AssertionError((rev, pc))

def fault_target(rev, pc):
    """Where a fault at the boundary before step pc sends the opener: the finally's first step, or None (done)."""
    o = opener_rev3() if rev == 3 else opener_rev2()
    if pc in o['try_']: return o['fin']
    return None

def explore(rev, split, budget, with_R=True):
    OP = opener_rev3() if rev == 3 else opener_rev2()
    start = ((0, 0, 0 if with_R else None), (None, None, None), False, frozenset(), frozenset(), budget, frozenset())
    # state: pcs (P1, P2, R), locals, S, A, flags, faults left, aborted-with-anchor set (dead anchors)
    seen = set(); stack = [(start, ())]
    res = dict(states=0, U1=[], A0=[], S0=[], END_stale_ff=0, END_stale_f=0, END_dead=0, END_dead_S=0, END_total=0,
               FLAG_ff=0, FLAG_f=0, U1_ff=0, U1_f=0, FLAGp=[])
    while stack:
        st, path = stack.pop()
        if st in seen: continue
        seen.add(st); res['states'] += 1
        pcs, locs, S, A, flags, left, dead = st
        live = A - dead
        # invariants on the state
        if live and not S:
            owners = [k for k in (0, 1) if pcs[k] is not None and (k + 1) in live and pcs[k] in OP['own_A']]
            owners += [k for k in (0, 1) if pcs[k] in OP['recheck']]
            if pcs[2] is not None and pcs[2] in OP['R_recheck']: owners.append(2)
            if not owners and len(res['A0']) < 3 and left == budget: res['A0'].append(path)
        if S and not A:
            inwin = [k for k in (0, 1) if pcs[k] is not None and pcs[k] in OP['own_S']]
            if pcs[2] is not None: inwin.append(2)
            if not inwin and left == budget and len(res['S0']) < 3: res['S0'].append(path)
        if all(p is None for p in pcs):
            res['END_total'] += 1
            if dead:
                res['END_dead'] += 1
                if S: res['END_dead_S'] += 1                                    # kept until that trace's exit (X3)
            elif S:                                                             # stale: one repair (_unwind_off) clears it
                res['END_stale_ff' if left == budget else 'END_stale_f'] += 1
            if any(x[0] == 'UNWIND_LOST' for x in flags):
                res['FLAG_ff' if left == budget else 'FLAG_f'] += 1
                if len(res['FLAGp']) < 3: res['FLAGp'].append(path)
            continue
        for k in (0, 1, 2):
            pc = pcs[k]
            if pc is None: continue
            if k < 2:
                npc, nloc, nS, nA, nfl, ev = step_opener(rev, k + 1, pc, locs[k], S, A, flags, split)
                if ev and ev[0] == 'hit' and not ev[1]:
                    if left == budget: res['U1_ff'] += 1
                    else: res['U1_f'] += 1
                    if len(res['U1']) < 3: res['U1'].append(path + (('P%d' % (k + 1), pc),))
                npcs = list(pcs); npcs[k] = npc; nlocs = list(locs); nlocs[k] = nloc
                ndead = dead | ({k + 1} if npc is None and (k + 1) in nA else frozenset())
                stack.append(((tuple(npcs), tuple(nlocs), nS, frozenset(nA), frozenset(nfl), left, frozenset(ndead)),
                              path + (('P%d' % (k + 1), pc),)))
                if left > 0:
                    tgt = fault_target(rev, pc)
                    if pc >= OP['fin']: tgt = None
                    npcs = list(pcs); npcs[k] = tgt; nlocs = list(locs); nlocs[k] = None
                    ndead = dead | ({k + 1} if tgt is None and (k + 1) in A else frozenset())
                    stack.append(((tuple(npcs), tuple(nlocs), S, A, flags, left - 1, frozenset(ndead)),
                                  path + (('P%d' % (k + 1), pc, 'FAULT'),)))
            else:
                npc, nS, nA = step_retirer(rev, pc, None, S, A, split)
                npcs = list(pcs); npcs[2] = npc
                stack.append(((tuple(npcs), locs, nS, nA, flags, left, dead), path + (('R', pc),)))
                if left > 0:
                    npcs = list(pcs); npcs[2] = None
                    stack.append(((tuple(npcs), locs, S, A, flags, left - 1, dead), path + (('R', pc, 'FAULT'),)))
    return res

def fmt(p): return ' '.join('%s%s%s' % (x[0], x[1], '!' if len(x) > 2 else '') for x in p)

for rev, split in ((2, False), (3, False), (3, True)):
    name = 'rev3-split' if split else 'rev%d' % rev
    for budget in (0, 1, 2):
        r = explore(rev, split, budget)
        print('%-10s faults<=%d: %6d states | U1 hits run with S clear: %d fault-free, %d on faulted paths | '
              'A0 (fault-free) %s | S0 (fault-free) %s | %d end states: stale S with no anchor %d fault-free, %d faulted '
              '(each cleared by one _unwind_off); dead anchor %d (S kept set in %d) | UNWIND_LOST: %d fault-free, %d faulted' % (
              name, budget, r['states'], r['U1_ff'], r['U1_f'],
              'ok' if not r['A0'] else 'VIOLATED', 'ok' if not r['S0'] else 'VIOLATED', r['END_total'],
              r['END_stale_ff'], r['END_stale_f'], r['END_dead'], r['END_dead_S'], r['FLAG_ff'], r['FLAG_f']))
        for key in ('U1', 'A0', 'S0', 'FLAGp'):
            if r[key]: print('    first %s trace:' % key, fmt(r[key][0]))
