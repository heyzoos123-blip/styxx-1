# Revision 7 (rev7/m7_modelcheck.py): rev6/m6_modelcheck.py copied, run for revision 6 and revision 7 (the seventh
# critic's B1 and M5):
#   REVISION 7    rev=7 is revision 6 plus two counting rules. (1) B1: every registration counts in _LOST each exchange
#                 whose previous callback was not styxx's, IN THE SAME STEP as that exchange (the spec counts inside
#                 the registration's consuming call), so every trace live then notes MONITOR_LOST. Mutant
#                 'cbrep_nocount' is revision 6 (no count); mutant 'count_after_register' is the seventh critic's
#                 proposed form (X5 counts after the registration returns, in a separate step), which a fault between
#                 the two steps defeats. (2) M5.2: _ensure_tool's fall-through may re-take the SAME id, when
#                 the reclaim's registration was split with owner None (the id is unowned again); a usable re-take
#                 while _TOOL[0] is set is counted like a rebinding (mutant 'retake_nocount' is revision 6's prototype
#                 rule). Revision 6's model never retried the same id; it moved to the other.
#   NEW OUTSIDE KIND  'cbrep0' replaces styxx's ENTRY callback ('cbrep' replaces the unwind callback, as before).
#   NEW CONFIGURATIONS (CONFIGS7)  callback replacement and local-events clears with TWO cores (the critic's c2 and
#                 its lclr twin, both orders of exit), and registrations at E4 and at the reclaim combined with a second
#                 live core, a raising hook (a fault at an audit-hook boundary) and a repeated free.
# Everything else is revision 6's model, unchanged.
#
# Revision 6 (rev6/m6_modelcheck.py): rev5/m5_modelcheck.py extended with what the sixth critic found missing (M2),
# run for revision 5 and revision 6 (revision 4's code paths are kept but not run):
#   REGISTRATION  _register is modelled with CPython's real behaviour: register_callback raises an audit event before
#                 its exchange, so a Python audit hook runs between each exchange's gate and the exchange. The five
#                 exchanges are abstracted to two (the entry/exit callbacks and the unwind callback): every audit-hook
#                 point is a step boundary, at which faults (a raising hook), re-entry, outside parties, thread
#                 switches and greenlet switches may land. Revision 5 gates once before all exchanges and reads nothing
#                 after them; revision 6 gates each exchange and reads the owner after the last one (M7). It is called
#                 at E4 (_ensure_tool: first acquisition, adoption, rebinding), at reconciliation's reclaim, and at X5.
#   CALLBACKS AND LOCAL EVENTS  each id carries a callback pair (entry/exit, unwind), each styxx's ('S'), another
#                 tool's ('F') or none ('N'), and the mint carries local events per id. A hit counts only if its entry
#                 and its unwind are delivered to styxx: (local events and styxx's entry callback on some id) and
#                 (global PY_UNWIND and styxx's unwind callback on some id). X5's two other note sources are modelled:
#                 a previous callback that is not styxx's, and a held mint whose local events on the id are not set.
#   REBINDING     two ids (4 and 3). _ensure_tool falls through to the other id when the one it holds was taken, and
#                 (revision 6) counts the rebinding and sets local events on the registered mint for the new id.
#   OUTSIDE PARTIES, COMBINED  outside events together with re-entry, greenlets and run_async; a kind may repeat
#                 (free -> reclaim -> free); new kinds: replace styxx's unwind callback ('cbrep'), clear the mint's
#                 local events ('lclr'); 'free' also applies to an id another tool holds (it frees its own).
#   THE PREMISE IS AN AXIOM  _unwind_on, _unwind_off, _take and _set_local are still ONE step each: the model assumes
#                 that nothing runs inside them (checked on CPython by G_ATOM, not here). _register is not one step.
# New properties: REGMULTI (more than one exchange of one registration lands on another tool's id), REGSILENT (at an
# end, a trace live when an exchange landed on another tool's id has a readable record without MONITOR_LOST);
# REGCLOB counts such exchanges (informational: the disclosed residual). CLOBBER now counts every other styxx write
# on an id another tool holds, revision 5's registration exchanges included (revision 5 claimed none).
#
# Exhaustive interleaving check of v5f's open / commit / close / exit / enter / reconcile protocol, revision 4 against
# revision 5, extended with everything the fifth critic found missing from rev4/m1_pairs_modelcheck.py:
#
#   RE-ENTRY     at any step boundary of any thread (inside any window, blocked waits included), a nested program may
#                run on that same thread to completion before the interrupted one continues: a whole section (a
#                signal handler or finalizer that calls cov.run), a run_async section left suspended when the nested
#                code returns (R19's shape), a user-code lock acquisition (a finalizer that needs a lock), or a whole
#                transaction (a finalizer that enters or exits a tracer);
#   BLOCKING     user locks: a thread may hold user lock L around its section or its exit (`with L: cov.run(...)`),
#                and a nested program may block on L; the busy bounds are modelled as a timeout step that a blocked
#                machinery wait may take at any time (MACHINERY_BUSY); user-lock waits have no timeout;
#   EXTERNAL     a party outside the machinery may, between any two steps, clear or set styxx's event, free styxx's
#                id, or take a freed id as another tool;
#   GREENLETS    a thread may hold two greenlets and switch between them at any step boundary; a switched-out
#                greenlet's frames are not on its thread's frame chain, so the liveness tests see them as dead;
#   RUN_ASYNC    an async section may suspend in its body (its anchor stays registered) and be resumed later by any
#                idle thread: on the same thread, or on another (a hop);
#   E4, RETIRE, RECLAIM   enter's transaction (reconcile, tool acquisition, mint: holder, register, local events,
#                install, credit, activate), _retire's steps, and reconciliation's reclaim of a freed, unowned id.
#
# Granularity: every single C operation is its own step. Revision 5's one-call steps are ONE step each: they are one
# C call, which no Python code, thread, signal, finalizer, instrument or greenlet can enter (t1_onecall_atomic.py).
#
# Properties (checked on every reachable state or transition; "ext" = an external event has happened in this run):
#   U1        no hit runs with the event clear while its anchor is registered and its core is crediting and alive,
#             unless ext (then it is recorded as a LOST hit, and LOSTNOTE below applies);
#   A0        no state has an armed, registered anchor of a crediting, live core with the event clear, unless ext;
#   STALE     no state has the event set with no anchor registered, unless an external party set the event or freed
#             or took the id (revision 5 only: revision 4 has these windows by design, and they are counted);
#   FALSEFLAG an UNWIND_LOST flag is set on a core only if some armed, registered anchor of that core has been seen
#             with the event clear (MONITOR_LOST completeness has a soundness half);
#   LOSTNOTE  (end, after repair) every core with a LOST hit whose record is readable carries MONITOR_LOST (or
#             MACHINERY_BUSY), unless an external set ended the blind interval first (MASKED: the disclosed residual);
#   CLOBBER   styxx never changes events, local events or callbacks of an id that another tool holds;
#   P8        no body runs whose opening was claimed, or whose core's exit had begun, before its anchor store;
#   HANG      no reachable state where live work exists and no step at all, timeouts included, is enabled;
#   CYC_OPEN  states where no thread can progress except through a timeout of an opener's wait (revision 4's MF1);
#   CYC_TX    the same through the robust mutex's timeout (the disclosed audit-hook/slow-owner residual);
#   BUSY_OPEN timeouts taken by an opener's wait (MACHINERY_BUSY at open);
#   END       (fault-free, no ext) no anchor, no event, no announcement, mutex and lock free, every appended opening
#             finalised, no flag;
#   REPAIR    (every end) after each unfinished core's exit and one reconciliation: no anchor, no event (on an id
#             styxx holds), no announcement, no mint registered or installed.
import sys, time

# ------------------------------------------------------------------ registers
(INTRY, OUT, NN, TXN, TOK, W, ONL, DFR, DARM, DS, DOID, DTAG, XL, XI, PL, PI, SL, SI, LATE, HOLDL, MARK, CAP,
 RETPC, PARKED, RGN, RGOWN, RGPOK, RGF, RGSITE) = range(29)
NREG = 29
def setr(regs, i, v): return regs[:i] + (v,) + regs[i + 1:]
def setrs(regs, **kw):
    r = list(regs)
    for k, v in kw.items(): r[globals()[k]] = v
    return tuple(r)

# frame = (kind, slot, core, pc, cs, regs, uid)
KIND, SLOT, CORE, PC, CS, REGS, UID = range(7)
def fset(fr, **kw):
    f = list(fr)
    for k, v in kw.items(): f[{'pc': PC, 'cs': CS, 'regs': REGS}[k]] = v
    return tuple(f)

# shared = (S, A, CLR, G, L, tool, lostn, cores, mint, ops, used, ghost, cb, oth)
#   S, tool, cb and mint[2] (local events) are the CURRENT id's (_TOOL[0]); oth = (tool, S, cb, lev) of the other id
S_, A_, CLR_, G_, L_, TOOL_, LOSTN_, CORES_, MINT_, OPS_, USED_, GHOST_, CB_, OTH_ = range(14)
# core = (ent, act, exi, exd, cred, fdead, flag, lost0, note)
ENT, ACT, EXI, EXD, CRED, FDEAD, FLAG, LOST0, NOTE = range(9)
# mint = (reg, inst, lev, holders) ; op = (app, frame, fin, armed)
# ghost = (ext, lost, a0raw, masked, extlist, regclob_cores)
def sset(sh, i, v): return sh[:i] + (v,) + sh[i + 1:]
def cset(sh, c, j, v):
    cs = sh[CORES_]; cr = cs[c]; cr = cr[:j] + (v,) + cr[j + 1:]
    return sset(sh, CORES_, cs[:c] + (cr,) + cs[c + 1:])
def oset(sh, o, j, v):
    os_ = sh[OPS_]; r = os_[o]; r = r[:j] + (v,) + r[j + 1:]
    return sset(sh, OPS_, os_[:o] + (r,) + os_[o + 1:])
def gset(sh, j, v):
    g = sh[GHOST_]; return sset(sh, GHOST_, g[:j] + (v,) + g[j + 1:])

class Cfg:
    def __init__(self, name, threads, ncores, covers, intr=(), intr_on=None, ext=(), faults=(0, 1), I=0, X=0, Wsw=0,
                 facade_dead=(), not_entered=(), slots=None, note='', xrep=1, fresh=False, oth_left=False):
        self.name, self.threads, self.ncores, self.covers = name, threads, ncores, covers
        self.intr, self.intr_on, self.ext, self.faults, self.I, self.X, self.Wsw = intr, intr_on, ext, faults, I, X, Wsw
        self.facade_dead, self.not_entered, self.note = facade_dead, not_entered, note
        self.xrep, self.fresh = xrep, fresh     # xrep: times an outside kind may occur; fresh: no id taken yet
        self.oth_left = oth_left                # revision 7: the other id is unowned but still carries styxx's callbacks
        # threads: list of greenlet lists: each program is (kind, core, slot)

class Model:
    def __init__(self, cfg, rev, mut=frozenset()):
        self.cfg, self.rev, self.mut = cfg, rev, mut
        self.op_core = {}
        for gl in cfg.threads:
            for p in gl:
                if p[2] is not None: self.op_core[p[2]] = p[1]
        for p in cfg.intr:
            if p[2] is not None: self.op_core[p[2]] = p[1]
        self.nslots = (max(self.op_core) + 1) if self.op_core else 0
        self.ext_kinds = cfg.ext

    # ---------------------------------------------------------------- helpers
    def newframe(self, kind, core, slot, uid):
        regs = [None] * NREG; regs[NN] = 0; regs[INTRY] = False
        pc = {'open': 'O2', 'aopen': 'O2', 'lockopen': 'L0', 'close': 'B_HIT', 'exit': 'X1', 'lockexit': 'L0',
              'enter': 'E0', 'rec': 'RA', 'lock': 'K_A'}[kind]
        if kind == 'close': regs[INTRY] = True
        return (kind, slot, core, pc, (), tuple(regs), uid)

    def alive(self, ths, tok, reg):
        if tok is None: return False
        uid = tok[0]; k, g = uid[0], uid[1]
        if k >= len(ths): return False
        gls, act, _ = ths[k]
        if act != g: return False
        for fr in gls[g]:
            if fr[UID] == uid and fr[REGS][reg] == tok: return True
        return False

    def core_dead(self, ths, sh, c):
        ent, act, exi, exd, cred, fdead, flag, lost0, note = sh[CORES_][c]
        if fdead or exd: return True
        if exi is not None and not self.alive(ths, exi, MARK): return True
        if not act and ent is not None and ent != 'pre' and not self.alive(ths, ent, MARK): return True
        return False

    def appended(self, sh, c):
        return tuple(o for o in range(self.nslots) if self.op_core.get(o) == c and sh[OPS_][o][0])

    def live_slots(self, ths, pk):
        """Openings whose owner can still run their body: inside _run's try, on a thread or parked."""
        out = set()
        for gls, act, ser in ths:
            for st in gls:
                for fr in st:
                    if fr[SLOT] is not None and fr[REGS][INTRY]: out.add(fr[SLOT])
        for fr in pk: out.add(fr[SLOT])
        return out

    def a0(self, ths, sh, need_cred, pk=None):
        """need_cred: the A0 violation (a live, armed, registered anchor of a crediting, live core with the event
        clear); otherwise the raw condition (armed and registered with the event clear), for flag soundness."""
        if (sh[S_] if not need_cred else self.delivered(sh)): return frozenset()
        out = set()
        live = self.live_slots(ths, pk or frozenset()) if need_cred else None
        for (key, o) in sh[A_]:
            c = self.op_core[o]
            if not sh[OPS_][o][3]: continue
            if need_cred and not (sh[CORES_][c][CRED] and not self.core_dead(ths, sh, c) and o in live): continue
            out.add(c)
        return frozenset(out)

    def delivered(self, sh):
        """A hit's entry and unwind reach styxx's callbacks on some id (revision-6 model)."""
        m = sh[MINT_]; cb = sh[CB_]; ot, oS, ocb, olev = sh[OTH_]
        entry = (m[2] and cb[0] == 'S') or (olev and ocb[0] == 'S')
        unwind = (sh[S_] and cb[1] == 'S') or (oS and ocb[1] == 'S')
        return entry and unwind

    def swap(self, sh):
        """_TOOL[0] moves to the other id: exchange the current id's state with the other's."""
        m = sh[MINT_]; ot, oS, ocb, olev = sh[OTH_]
        sh2 = sset(sset(sset(sh, S_, oS), TOOL_, ot), CB_, ocb)
        sh2 = sset(sh2, MINT_, (m[0], m[1], olev, m[3]))
        return sset(sh2, OTH_, (sh[TOOL_], sh[S_], sh[CB_], m[2]))

    def live_cores(self, sh):
        return frozenset(c for c in range(self.cfg.ncores)
                         if sh[CORES_][c][ACT] and sh[CORES_][c][EXI] is None and not sh[CORES_][c][EXD])

    def write(self, sh, ev):
        """A styxx write to its id (set_events, set_local_events, register_callback): CLOBBER if the id is another's."""
        if sh[TOOL_] == 'other': ev.append('CLOBBER')
        return sh

    # ---------------------------------------------------------------- initial
    def initial(self):
        cfg = self.cfg
        cores = []
        for c in range(cfg.ncores):
            if c in cfg.not_entered: cores.append((None, False, None, False, False, c in cfg.facade_dead, False, 0, None))
            else: cores.append(('pre', True, None, False, True, c in cfg.facade_dead, False, 0, None))
        holders = frozenset(c for c in range(cfg.ncores) if c not in cfg.not_entered)
        mint = (bool(holders), bool(holders), bool(holders), holders)
        ops = [(False, None, None, False)] * self.nslots
        S = False; A = frozenset()
        ths = []
        for k, gl in enumerate(cfg.threads):
            stacks = [] if gl else [()]
            for gi, p in enumerate(gl):
                kind, core, slot = p
                fr = self.newframe(kind, core, slot, (k, gi, 0))
                if kind == 'close':
                    ops[slot] = (True, slot, None, True); A = A | {(slot, slot)}; S = True
                    fr = fset(fr, regs=setr(fr[REGS], OUT, 'ran'))
                stacks.append((fr,))
            ths.append((tuple(stacks), 0, 1))
        ghost = (frozenset(), frozenset(), frozenset(), frozenset(), (), frozenset())
        tool0, cb0 = ('none', ('N', 'N')) if cfg.fresh else ('ours', ('S', 'S'))
        sh = (S, A, frozenset(), None, None, tool0, 0, tuple(cores), mint, tuple(ops), frozenset(), ghost, cb0,
              ('none', False, ('S', 'S') if cfg.oth_left else ('N', 'N'), False))
        return tuple(ths), sh, frozenset()

    # ---------------------------------------------------------------- thread-structure helpers
    def top(self, ths, k):
        gls, act, ser = ths[k]
        st = gls[act]
        return st[-1] if st else None
    def settop(self, ths, k, fr):
        gls, act, ser = ths[k]
        st = gls[act][:-1] + (fr,)
        return ths[:k] + ((gls[:act] + (st,) + gls[act + 1:], act, ser),) + ths[k + 1:]
    def poptop(self, ths, k):
        gls, act, ser = ths[k]
        st = gls[act][:-1]
        gls = gls[:act] + (st,) + gls[act + 1:]
        if not st:                                   # a finished greenlet: its parent (the next non-empty) resumes
            for gi, s in enumerate(gls):
                if s: act = gi; break
        return ths[:k] + ((gls, act, ser),) + ths[k + 1:]
    def push(self, ths, k, kind, core, slot):
        gls, act, ser = ths[k]
        fr = self.newframe(kind, core, slot, (k, act, ser))
        st = gls[act] + (fr,)
        return ths[:k] + ((gls[:act] + (st,) + gls[act + 1:], act, ser + 1),) + ths[k + 1:]
    def pushframe(self, ths, k, fr):
        gls, act, ser = ths[k]
        fr = fr[:UID] + ((k, act, ser),)
        st = gls[act] + (fr,)
        return ths[:k] + ((gls[:act] + (st,) + gls[act + 1:], act, ser + 1),) + ths[k + 1:]
    def idle(self, ths, k):
        gls, act, ser = ths[k]
        return not any(gls)
    def holds_lock(self, ths, k):
        gls, act, ser = ths[k]
        return any(fr[REGS][HOLDL] for st in gls for fr in st)

    # ---------------------------------------------------------------- one step of thread k's top frame
    def step(self, ths, sh, pk, k):
        fr = self.top(ths, k)
        if fr is None: return []
        kind, slot, core, pc, cs, r, uid = fr
        rev, mut = self.rev, self.mut
        S, A, CLR, G, L, tool = sh[S_], sh[A_], sh[CLR_], sh[G_], sh[L_], sh[TOOL_]
        cores, ops = sh[CORES_], sh[OPS_]
        ev = []
        o = slot
        def upd(pc2=None, cs2=None, r2=None, sh2=None, pk2=None):
            f2 = (kind, slot, core, pc2 if pc2 is not None else pc, cs2 if cs2 is not None else cs,
                  r2 if r2 is not None else r, uid)
            return [(self.settop(ths, k, f2), sh2 if sh2 is not None else sh, pk2 if pk2 is not None else pk, ev)]
        def call(sub, ret, r2=None, sh2=None):
            return upd(pc2=sub, cs2=cs + (ret,), r2=r2, sh2=sh2)
        def ret_(r2=None, sh2=None):
            return upd(pc2=cs[-1], cs2=cs[:-1], r2=r2, sh2=sh2)
        def end(sh2=None, r2=None):
            sh2 = sh2 if sh2 is not None else sh
            if (r2 if r2 is not None else r)[HOLDL] and sh2[L_] == k: sh2 = sset(sh2, L_, None)
            return [(self.poptop(ths, k), sh2, pk, ev)]
        def tok_new(reg):
            t = (uid, r[NN]); return t, setr(setr(r, NN, r[NN] + 1), reg, t)

        # ======================= user lock =======================
        if pc == 'L0' or pc == 'K_A':
            if L is not None and L != k: return []   # blocked on the user lock (no timeout)
            nxt = {'lockopen': 'O2', 'lockexit': 'X1', 'lock': 'K_R'}[kind]
            return upd(pc2=nxt, r2=setr(r, HOLDL, True), sh2=sset(sh, L_, k))
        if pc == 'K_R':
            return end(sh2=sset(sh, L_, None), r2=setr(r, HOLDL, False))
        if pc == 'FIN_L':
            return end()
        # ======================= opener =======================
        if pc == 'O2':
            c = self.op_core[o]
            if not cores[c][ACT] or cores[c][EXI] is not None or cores[c][EXD]:
                return upd(pc2='FIN_L', r2=setr(r, OUT, 'inactive@open'))
            return upd(pc2='O6')
        if pc == 'O6':
            return upd(pc2='OT', sh2=sset(sh, OPS_, ops[:o] + ((True, o, None, False),) + ops[o + 1:]))
        if pc == 'OT':
            nxt = 'C_ON0' if (rev >= 5 and 'on_before_store' in mut) else 'C_ST'
            return upd(pc2=nxt, r2=setr(r, INTRY, True))
        if pc == 'C_ON0':                                # mutant: revision 3's first set, before the store, ungated
            sh2 = sh if (S or tool != 'ours') else self.write(sset(sh, S_, True), ev)
            return upd(pc2='C_ST', sh2=sh2)
        if pc == 'C_ST':
            key = ops[o][1]; c = self.op_core[o]
            late = ops[o][2] is not None or cores[c][EXI] is not None
            return upd(pc2='C_CK', r2=setr(r, LATE, late), sh2=sset(sh, A_, A | {(key, o)}))
        if pc == 'C_CK':
            c = self.op_core[o]
            if 'no_recheck' in mut:
                return upd(pc2='C_PRE')
            claimed = ops[o][2] is not None and 'no_fin_test' not in mut
            exiting = cores[c][EXI] is not None and 'no_exiting_test' not in mut
            if claimed or exiting:
                r2 = setrs(r, DOID=o, DTAG='open', OUT='inactive@commit')
                return call('D_CLAIM', 'C_RAISE', r2=r2)
            return upd(pc2='C_PRE')
        if pc == 'C_RAISE':
            return upd(pc2='F_D', cs2=(), r2=setr(r, INTRY, False))
        if pc == 'C_PRE':
            if rev == 4: return upd(pc2='C_SN')
            if 'no_on' in mut or 'on_before_store' in mut: return upd(pc2='C_AR')
            if 'on_capture_split' in mut: return upd(pc2='C_ONr')
            if 'gate_split' in mut: return upd(pc2='C_ONg')
            return upd(pc2='C_ON', r2=setr(r, ONL, None))
        if pc == 'C_ONg':                                # mutant gate_split: the name test as its own step
            return upd(pc2='C_ON', r2=setr(r, ONL, tool == 'ours'))
        # ---- revision 5: ON, one step ----
        if pc == 'C_ON':
            own = (ops[o][1], o) in A or 'on_ungated_own' in mut
            sh2 = sh
            ours = (tool == 'ours') if r[ONL] is None else r[ONL]
            if ours and own and r[ONL] is not None and tool != 'ours' and not S:
                if tool == 'freed': return self.raise_(ths, sh, pk, k, fr, ev)
                return upd(pc2='C_AR', sh2=self.write(sset(sh, S_, True), ev))
            if ours and own:
                if not S or 'on_capture_nogate' in mut:
                    if 'on_no_capture' not in mut:
                        for (key, p) in A:
                            if ops[p][3]: sh2 = self.flag(ths, sh2, self.op_core[p], ev)
                if not S: sh2 = sset(sh2, S_, True)
            return upd(pc2='C_AR', sh2=sh2)
        if pc == 'C_ONr':                                # mutant: read in one call ...
            clear = tool == 'ours' and not S and (ops[o][1], o) in A
            return upd(pc2='C_ONw', r2=setr(r, CAP, clear))
        if pc == 'C_ONw':                                # ... capture and set in another
            sh2 = sh
            if r[CAP]:
                for (key, p) in A:
                    if ops[p][3]: sh2 = self.flag(ths, sh2, self.op_core[p], ev)
                sh2 = self.write(sset(sh2, S_, True), ev)
            return upd(pc2='C_AR', sh2=sh2)
        # ---- revision 4: snapshot, wait, read, set ----
        if pc == 'C_SN':
            snap = frozenset(t for t in CLR if t[0][0] != k)
            return upd(pc2='C_WT', r2=setr(r, W, snap))
        if pc == 'C_WT':
            for t in r[W]:
                if t in CLR and self.alive(ths, t, TOK): return []   # blocked (timeout possible)
            return upd(pc2='C_OR')
        if pc == 'C_OR':
            return upd(pc2='C_OS', r2=setr(r, ONL, (tool == 'ours', S)))
        if pc == 'C_OS':
            ours, s = r[ONL]; sh2 = sh
            if ours and not s:
                if tool == 'freed': return self.raise_(ths, sh, pk, k, fr, ev)     # set_events on a freed id
                sh2 = self.write(sset(sh, S_, True), ev)
            return upd(pc2='C_AR', sh2=sh2)
        if pc == 'C_AR':
            nxt = 'B_PARK' if kind == 'aopen' and not r[PARKED] else 'B_HIT'
            return upd(pc2=nxt, sh2=oset(sh, o, 3, True))
        # ---- body ----
        if pc == 'B_PARK':                               # run_async: suspend in the body; any idle thread resumes it
            f2 = (kind, slot, core, 'B_HIT', cs, setr(r, PARKED, True), None)
            return [(self.poptop(ths, k), sh, pk | {f2}, ev)]
        if pc == 'B_HIT':
            c = self.op_core[o]
            blind = (not self.delivered(sh)) and (ops[o][1], o) in A and cores[c][CRED] and not self.core_dead(ths, sh, c)
            sh2 = sh
            if blind:
                if not sh[GHOST_][0]: ev.append('U1')
                sh2 = gset(sh2, 1, sh[GHOST_][1] | {c})
            if r[LATE]: ev.append('P8')
            return upd(pc2='B_END', r2=setr(r, OUT, 'ran'), sh2=sh2)
        if pc == 'B_END':
            return upd(pc2='F_D', r2=setr(r, INTRY, False))
        if pc == 'F_D':
            return call('D_CLAIM', 'F_N', r2=setrs(r, DOID=o, DTAG='closed'))
        if pc == 'F_N':
            return upd(pc2='FIN_L', sh2=oset(sh, o, 1, None))   # the owner releases the anchor frame
        # ======================= _detach(DOID) =======================
        if pc == 'D_CLAIM':
            d = r[DOID]
            sh2 = sh if ops[d][2] is not None else oset(sh, d, 2, r[DTAG])
            return upd(pc2='D_FR', sh2=sh2)
        if pc == 'D_FR':
            d = r[DOID]; fr_ = ops[d][1]
            if fr_ is None:
                if rev >= 5: return ret_()
                return upd(pc2='D_OFF', r2=setr(r, DFR, None))
            return upd(pc2='D_ARM', r2=setr(r, DFR, fr_))
        if pc == 'D_ARM':
            d = r[DOID]
            nxt = 'D_A' if 'blind_anchor_first' in mut else 'D_S'
            return upd(pc2=nxt, r2=setr(r, DARM, ops[d][3] or 'blind_no_armed' in mut))
        if pc == 'D_S':                                  # the event first (rev 5: a plain read; get_events never raises)
            return upd(pc2='D_A4', r2=setr(r, DS, (not S) and (tool == 'ours' or (rev >= 5 and 'blind_read_gated' not in mut))))
        if pc == 'D_A4':                                 # ... the anchor last
            d = r[DOID]; reg = (r[DFR], d) in A or 'blind_no_anchor' in mut
            sh2 = sh
            if r[DARM] and r[DS] and reg: sh2 = self.flag(ths, sh, self.op_core[d], ev)
            return upd(pc2=self.after_blind(), sh2=sh2)
        if pc == 'D_A':                                  # mutant: the anchor first ...
            d = r[DOID]
            return upd(pc2='D_S2', r2=setr(r, DS, (r[DFR], d) in A))
        if pc == 'D_S2':                                 # ... then the event
            d = r[DOID]; sh2 = sh
            if r[DARM] and r[DS] and not S and (tool == 'ours' or rev >= 5): sh2 = self.flag(ths, sh, self.op_core[d], ev)
            return upd(pc2=self.after_blind(), sh2=sh2)
        if pc == 'D_POg':                                # mutant gate_split: the name test as its own step
            return upd(pc2='D_PO', r2=setr(r, ONL, tool == 'ours'))
        if pc == 'D_PO':                                 # revision 5: ONE step: pop, then clear iff nothing is left
            fr_ = r[DFR]
            A2 = frozenset(x for x in A if x[0] != fr_)
            sh2 = sset(sh, A_, A2)
            if 'detach_nulls' in mut: sh2 = oset(sh2, r[DOID], 1, None)   # revision 3's release by every detacher
            if 'gate_split' in mut:
                if not A2 and r[ONL]:
                    if tool == 'freed': return self.raise_(ths, sh2, pk, k, fr, ev)
                    sh2 = self.write(sset(sh2, S_, False), ev)
                return ret_(sh2=sh2)
            if not A2 and tool == 'ours': sh2 = sset(sh2, S_, False)
            return ret_(sh2=sh2)
        if pc == 'D_POP':
            fr_ = r[DFR]
            sh2 = sset(sh, A_, frozenset(x for x in A if x[0] != fr_))
            if rev == 4:
                if 'detach_nulls' in mut: sh2 = oset(sh2, r[DOID], 1, None)
                return upd(pc2='D_OFF', sh2=sh2)
            if 'off_split' in mut: return upd(pc2='U5_T', sh2=sh2)
            return upd(pc2='D_OFF1', sh2=sh2)          # popoff_split
        if pc == 'D_OFF1':                               # mutant popoff_split: OFF as its own one call
            sh2 = sh
            if not A and tool == 'ours': sh2 = sset(sh, S_, False)
            return ret_(sh2=sh2)
        if pc == 'U5_T':                                 # mutant off_split: the test ...
            return upd(pc2='U5_C', r2=setr(r, ONL, (not A) and tool == 'ours'))
        if pc == 'U5_C':                                 # ... then the clear
            sh2 = sh
            if r[ONL]:
                if tool == 'freed': return self.raise_(ths, sh, pk, k, fr, ev)
                sh2 = self.write(sset(sh, S_, False), ev)
            return ret_(sh2=sh2)
        if pc == 'D_OFF':                                # revision 4: _unwind_off after the pop
            return call('U_R', 'D_RET')
        if pc == 'D_RET':
            return ret_()
        # ======================= revision 4 _unwind_off =======================
        if pc == 'U_R':
            if tool != 'ours' or not S: return ret_()
            return upd(pc2='U_AN')
        if pc == 'U_AN':
            t, r2 = tok_new(TOK)
            return upd(pc2='U_T', r2=r2, sh2=sset(sh, CLR_, CLR | {t}))
        if pc == 'U_T':
            if A: return upd(pc2='U_WD')
            return upd(pc2='U_C')
        if pc == 'U_C':
            if tool == 'freed': return self.raise_(ths, sh, pk, k, fr, ev)
            return upd(pc2='U_WD', sh2=self.write(sset(sh, S_, False), ev))
        if pc == 'U_WD':
            return ret_(r2=setr(r, TOK, None), sh2=sset(sh, CLR_, CLR - {r[TOK]}))
        # ======================= exit =======================
        if pc == 'X1':
            c = core
            if cores[c][EXI] is not None or cores[c][EXD] or not cores[c][ACT]:
                return upd(pc2='FIN_L')
            t, r2 = tok_new(MARK)
            return upd(pc2='X2', r2=r2, sh2=cset(sh, c, EXI, t))
        if pc == 'X2':
            return upd(pc2='X3S', sh2=cset(sh, core, CRED, False))
        if pc == 'X3S':
            return upd(pc2='X3L', r2=setrs(r, XL=self.appended(sh, core), XI=0))
        if pc == 'X3L':
            if r[XI] < len(r[XL]):
                d = r[XL][r[XI]]
                return call('D_CLAIM', 'X3L', r2=setrs(r, XI=r[XI] + 1, DOID=d, DTAG='open'))
            return upd(pc2='X5A')
        if pc in ('X5A', 'E4A', 'RA'):
            if G is not None and self.alive(ths, G, TXN):
                if G[0][0] == k:                         # a live owner on this thread: REENTRANT (a GateSpecError)
                    ev.append('REENT')
                    return self.gse(ths, sh, pk, k, fr, ev)
                return []                                # blocked on the mutex (timeout possible)
            t, r2 = tok_new(TXN)
            nxt = {'X5A': 'X5T', 'E4A': 'E4T', 'RA': 'RZ'}[pc]
            return call('R0', nxt, r2=r2, sh2=sset(sh, G_, t))
        if pc == 'X5T' and rev >= 5:                     # revision 5 and 6: the MONITOR_LOST test with the registration
            if self.reg5() and tool != 'ours':           # revision 5: the name test first; not ours -> old branch
                return upd(pc2='X5T4')
            return call('RG1', 'X5N', r2=setr(r, RGSITE, 'exit'))
        if pc == 'X5N':
            c = core; m = sh[MINT_]
            ok = self.reg_ok(r, tool)
            sh2 = sh
            held_lev_bad = ok and m[0] and c in m[3] and not m[2]
            note = (cores[c][FLAG] or sh[LOSTN_] != cores[c][LOST0] or not ok or not r[RGPOK] or held_lev_bad)
            sh2 = cset(sh2, c, NOTE, note)
            if self.rev >= 7 and ok and not r[RGPOK] and 'count_after_register' in mut:   # the critic's form: a count after the call
                sh2 = sset(sh2, LOSTN_, sh2[LOSTN_] + 1)
            m = sh2[MINT_]
            holders = m[3] - {c}
            sh2 = sset(sh2, MINT_, (m[0], m[1], m[2], holders))
            if not holders and m[0] and ok:
                return call('RT1', 'X5Z', sh2=sh2)
            if not holders and m[0]:                     # the id is not ours: never touched again (restore only)
                return upd(pc2='X5Z', sh2=sset(sh2, MINT_, (False, False, m[2], holders)))
            return upd(pc2='X5Z', sh2=sh2)
        if pc in ('X5T', 'X5T4'):                        # the MONITOR_LOST test (revision 4; revision 5 on a lost id)
            c = core
            note = cores[c][FLAG] or sh[LOSTN_] != cores[c][LOST0] or tool != 'ours'
            sh2 = cset(sh, c, NOTE, note)
            m = sh[MINT_]
            holders = m[3] - {c}
            sh2 = sset(sh2, MINT_, (m[0], m[1], m[2], holders))
            if not holders and m[0] and tool == 'ours':
                return call('RT1', 'X5Z', sh2=sh2)
            if not holders and m[0]:                     # the id is not ours: never touched again (restore only)
                return upd(pc2='X5Z', sh2=sset(sh2, MINT_, (False, False, m[2], holders)))
            return upd(pc2='X5Z', sh2=sh2)
        if pc in ('X5Z', 'RZ', 'E4Z'):
            sh2 = sset(sh, G_, None) if G == r[TXN] else sh
            r2 = setr(r, TXN, None)
            if pc == 'RZ': return end(sh2=sh2, r2=r2)
            if pc == 'E4Z': return upd(pc2='E5', r2=r2, sh2=sh2)
            return upd(pc2='X8', r2=r2, sh2=sh2)
        if pc == 'X8':
            return upd(pc2='FIN_L', sh2=cset(sh, core, EXD, True))
        # ======================= enter =======================
        if pc == 'E0':
            c = core
            if cores[c][ENT] is not None: return upd(pc2='FIN_L', r2=setr(r, OUT, 'REENTRY'))
            t, r2 = tok_new(MARK)
            return upd(pc2='E4A', r2=r2, sh2=cset(sh, c, ENT, t))
        if pc == 'E4T' and rev >= 5:                     # _ensure_tool (revision 5 as specified; revision 6)
            if tool == 'ours': return upd(pc2='E4M')
            if tool == 'freed':                          # our own id, freed: re-taken through _reclaim
                if 'take_split' in mut: return upd(pc2='E4U', r2=setr(r, ONL, True))
                return call('RG1', 'E4K', r2=setr(r, RGSITE, 'reclaim'), sh2=sset(sh, TOOL_, 'ours'))
            if tool == 'none':                           # first acquisition (_TOOL[0] unset): take this id
                return call('RG1', 'E4F', r2=setr(r, RGSITE, 'first'), sh2=sset(sh, TOOL_, 'ours'))
            return upd(pc2='E4B', r2=setr(r, RGSITE, 'rebind'))
        if pc == 'E4K':                                  # after the reclaim's registration
            ok = self.reg_ok(r, tool)
            count = (ok if not self.reg5() else tool == 'ours')
            sh2 = sset(sh, LOSTN_, sh[LOSTN_] + 1) if (count and 'ensure_nocount' not in mut) else sh
            if ok and tool == 'ours': return upd(pc2='E4M', sh2=sh2)
            if self.rev >= 7 and tool == 'freed':        # revision 7 (M5.2): the fall-through re-takes the same, unowned id
                return call('RG1', 'E4RK', r2=setr(r, RGSITE, 'retake'), sh2=sset(sh2, TOOL_, 'ours'))
            return upd(pc2='E4B', r2=setr(r, RGSITE, 'rebind'), sh2=sh2)
        if pc == 'E4RK':                                 # revision 7: after the re-take's registration
            if not (self.reg_ok(r, tool) and tool == 'ours'): return upd(pc2='E4B', r2=setr(r, RGSITE, 'rebind'))
            sh2 = sh
            if 'retake_nocount' not in mut: sh2 = sset(sh2, LOSTN_, sh[LOSTN_] + 1)
            m = sh2[MINT_]
            if m[0]: sh2 = sset(sh2, MINT_, (m[0], m[1], True, m[3]))
            return upd(pc2='E4M', sh2=sh2)
        if pc == 'E4F':                                  # after the first acquisition's registration
            if self.reg_ok(r, tool) and tool == 'ours': return upd(pc2='E4M')
            return upd(pc2='E4B', r2=setr(r, RGSITE, 'first'))
        if pc == 'E4B':                                  # the other id (4 then 3): adopt, or take if unowned
            ot = sh[OTH_][0]
            if ot not in ('none', 'freed', 'ours'): return self.gse(ths, sh, pk, k, fr, ev)   # MONITOR_BUSY
            sh2 = self.swap(sh)
            sh2 = sset(sh2, TOOL_, 'ours')
            return call('RG1', 'E4BK', r2=setr(r, ONL, r[RGSITE]), sh2=sh2)
        if pc == 'E4BK':
            if not (self.reg_ok(r, tool) and tool == 'ours'):
                return self.gse(ths, self.swap(sh), pk, k, fr, ev)   # neither id usable: MONITOR_BUSY; _TOOL[0] unchanged
            sh2 = sh
            if r[ONL] == 'rebind' and not self.reg5():  # revision 6 (N1): count the rebinding; local events for the mint
                if 'rebind_count_none' not in mut: sh2 = sset(sh2, LOSTN_, sh[LOSTN_] + 1)
                m = sh2[MINT_]
                if m[0] and 'rebind_no_local' not in mut: sh2 = sset(sh2, MINT_, (m[0], m[1], True, m[3]))
            return upd(pc2='E4M', sh2=sh2)
        if pc == 'E4T':                                  # _ensure_tool (revision 4)
            if tool == 'ours': return upd(pc2='E4M')
            if tool == 'freed':
                return upd(pc2='E4U', r2=setr(r, ONL, True))
            return self.gse(ths, sh, pk, k, fr, ev)     # held by another tool: (id 3 in the spec) not modelled: refuse
        if pc == 'E4U':                                  # revision 4 (and take_split): use_tool_id after the test
            if tool != 'freed': return self.raise_(ths, sh, pk, k, fr, ev)            # ValueError: taken meanwhile
            if rev >= 5: return call('RG1', 'E4K', r2=setr(r, RGSITE, 'reclaim'), sh2=sset(sh, TOOL_, 'ours'))
            return upd(pc2='E4M', sh2=sset(sh, TOOL_, 'ours'))
        if pc == 'E4M':
            m = sh[MINT_]
            sh2 = sset(sh, MINT_, (True, m[1], m[2], m[3] | {core}))
            if m[0]: return upd(pc2='E4C', sh2=sh2)
            return upd(pc2='E4L', sh2=sh2)
        if pc == 'E4L':
            m = sh[MINT_]
            if rev >= 5 and 'gate_split' not in mut:    # one gated call
                if tool != 'ours': return upd(pc2='E4I')
                return upd(pc2='E4I', sh2=sset(sh, MINT_, (m[0], m[1], True, m[3])))
            return upd(pc2='E4Lw', r2=setr(r, ONL, tool == 'ours'))
        if pc == 'E4Lw':                                 # revision 4 (and gate_split): the write after the test
            m = sh[MINT_]
            if not r[ONL]: return upd(pc2='E4I')
            if tool == 'freed': return self.raise_(ths, sh, pk, k, fr, ev)
            return upd(pc2='E4I', sh2=self.write(sset(sh, MINT_, (m[0], m[1], True, m[3])), ev))
        if pc == 'E4I':
            m = sh[MINT_]
            return upd(pc2='E4C', sh2=sset(sh, MINT_, (m[0], True, m[2], m[3])))
        if pc == 'E4C':
            sh2 = cset(sh, core, CRED, True); sh2 = cset(sh2, core, LOST0, sh[LOSTN_])
            return upd(pc2='E4Z', sh2=sh2)
        if pc == 'E5':
            return upd(pc2='FIN_L', sh2=cset(sh, core, ACT, True))
        # ======================= reconciliation =======================
        if pc == 'R0':                                   # step 0: reclaim a freed, unowned id
            if tool == 'freed':
                if rev >= 5 and 'take_split' not in mut:  # _take (one step), then _register (audit hooks inside)
                    return call('RG1', 'R0C', r2=setr(r, RGSITE, 'reclaim'), sh2=sset(sh, TOOL_, 'ours'))
                return upd(pc2='R0U')
            return upd(pc2='R_P')
        if pc == 'R0U':
            if tool != 'freed': return self.raise_(ths, sh, pk, k, fr, ev)
            if rev >= 5: return call('RG1', 'R0C', r2=setr(r, RGSITE, 'reclaim'), sh2=sset(sh, TOOL_, 'ours'))
            return upd(pc2='R_P', sh2=sset(sset(sh, TOOL_, 'ours'), LOSTN_, sh[LOSTN_] + 1))
        if pc == 'R0C':                                  # step 3: count the re-take (revision 6: or a split's owner)
            if self.reg5(): count = tool == 'ours'
            else:
                count = self.reg_ok(r, tool)
            return upd(pc2='R_P', sh2=sset(sh, LOSTN_, sh[LOSTN_] + 1) if count else sh)
        # ======================= _register (audit hooks inside every exchange; revisions 5 and 6) =======================
        if pc == 'RG1':                                  # the first gate
            r2 = setrs(r, RGN=0, RGF=0, RGPOK=True, RGOWN=None)
            if tool != 'ours': return ret_(r2=setr(r2, RGOWN, tool))
            return upd(pc2='RGX1', r2=r2)                # the audit hook of exchange 1 runs here (a step boundary)
        if pc in ('RGX1', 'RGX2'):                       # exchange i, then (revision 6) gate i+1 or the owner read
            i = 0 if pc == 'RGX1' else 1
            cb = sh[CB_]
            r2 = setrs(r, RGN=i + 1, RGPOK=r[RGPOK] and cb[i] == 'S')
            sh2 = sset(sh, CB_, cb[:i] + ('S',) + cb[i + 1:])
            if (self.rev >= 7 and cb[i] != 'S' and 'cbrep_nocount' not in mut and 'count_after_register' not in mut):
                sh2 = sset(sh2, LOSTN_, sh2[LOSTN_] + 1)   # revision 7 (B1): counted in the same step as the exchange
            if tool == 'other':                          # this exchange landed on another tool's id
                r2 = setr(r2, RGF, r[RGF] + 1)
                ev.append('CLOBBER' if self.reg5() else 'REGCLOB')
                if r2[RGF] > 1: ev.append('REGMULTI')
                g = self.live_cores(sh2) | ({core} if r[RGSITE] == 'exit' else frozenset())
                sh2 = gset(sh2, 5, sh2[GHOST_][5] | g)
            if i == 1 or (not self.reg5() and tool != 'ours'):
                return ret_(r2=setr(r2, RGOWN, tool if not self.reg5() else None), sh2=sh2)
            return upd(pc2='RGX2', r2=r2, sh2=sh2)
        if pc == 'R_P':                                  # prune: dead holders
            m = sh[MINT_]; dead = [c for c in sorted(m[3]) if self.core_dead(ths, sh, c) and not cores[c][EXD]]
            sh2 = sh; lst = ()
            for c in dead:
                if rev == 4 or 'prune_credit_stop' in mut: sh2 = cset(sh2, c, CRED, False)
                lst += self.appended(sh, c)
            return upd(pc2='R_PL', r2=setrs(r, PL=lst, PI=0), sh2=sh2)
        if pc == 'R_PL':
            if r[PI] < len(r[PL]):
                d = r[PL][r[PI]]
                return call('D_CLAIM', 'R_PL', r2=setrs(r, PI=r[PI] + 1, DOID=d, DTAG='pruned'))
            return upd(pc2='R_PH')
        if pc == 'R_PH':
            m = sh[MINT_]
            keep = frozenset(c for c in m[3] if not self.core_dead(ths, sh, c))
            sh2 = sset(sh, MINT_, (m[0], m[1], m[2], keep))
            if not keep and m[0]:
                if tool == 'ours': return call('RT1', 'R_S', sh2=sh2)
                return upd(pc2='R_S', sh2=sset(sh2, MINT_, (False, False, m[2], keep)))
            return upd(pc2='R_S', sh2=sh2)
        if pc == 'R_S':                                  # anchors of dead cores (rev 4: the sweep; rev 5: pruned too)
            if 'no_anchor_prune' in mut or 'no_anchor_sweep' in mut: return upd(pc2='R_TK')
            lst = tuple(sorted(x for x in A if self.core_dead(ths, sh, self.op_core[x[1]])))
            return upd(pc2='R_SL', r2=setrs(r, SL=lst, SI=0))
        if pc == 'R_SL':
            if r[SI] < len(r[SL]):
                d = r[SL][r[SI]][1]
                sh2 = sh
                if rev == 4 and 'sweep_no_credit_stop' not in mut: sh2 = cset(sh, self.op_core[d], CRED, False)
                return call('D_CLAIM', 'R_SP', r2=setrs(r, DOID=d, DTAG='pruned'), sh2=sh2)
            return upd(pc2='R_TK')
        if pc == 'R_SP':
            x = r[SL][r[SI]]
            return upd(pc2='R_SL', r2=setr(r, SI, r[SI] + 1), sh2=sset(sh, A_, A - {x}))
        if pc == 'R_TK':
            if rev == 4:
                return upd(pc2='R_OFF', sh2=sset(sh, CLR_, frozenset(t for t in CLR if self.alive(ths, t, TOK))))
            return upd(pc2='R_OFF')
        if pc == 'R_OFF':
            if rev == 4: return call('U_R', 'R_RET')
            if 'no_rec_off' in mut: return ret_()
            sh2 = sh
            if not A and tool == 'ours': sh2 = sset(sh, S_, False)
            return ret_(sh2=sh2)                         # revision 5: one call OFF(None)
        if pc == 'R_RET':
            return ret_()
        # ======================= _retire =======================
        if pc == 'RT1':
            m = sh[MINT_]; return upd(pc2='RT2', sh2=sset(sh, MINT_, (m[0], False, m[2], m[3])))
        if pc == 'RT2':                                  # local events off: one gated call (rev 5), test+write (rev 4)
            m = sh[MINT_]
            if rev >= 5 and 'gate_split' not in mut:
                if tool == 'ours': return upd(pc2='RT3', sh2=sset(sh, MINT_, (m[0], m[1], False, m[3])))
                return upd(pc2='RT3')
            return upd(pc2='RT2w', r2=setr(r, ONL, tool == 'ours'))
        if pc == 'RT2w':
            m = sh[MINT_]
            if not r[ONL]: return upd(pc2='RT3')
            if tool == 'freed': return self.raise_(ths, sh, pk, k, fr, ev)
            return upd(pc2='RT3', sh2=self.write(sset(sh, MINT_, (m[0], m[1], False, m[3])), ev))
        if pc == 'RT3':
            m = sh[MINT_]; sh2 = sset(sh, MINT_, (False, m[1], m[2], m[3]))
            if rev == 4: return call('U_R', 'RT_RET', sh2=sh2)   # revision 4's step 6
            return ret_(sh2=sh2)
        if pc == 'RT_RET':
            return ret_()
        raise AssertionError((kind, pc))

    def reg5(self):
        return self.rev == 5 or 'reg_rev5' in self.mut

    def reg_ok(self, r, tool):
        """Revision 6: both exchanges made and the owner read after the last one is styxx. Revision 5 reads nothing
        after its registration: it proceeds as if it held the id."""
        if self.reg5(): return True
        return r[RGN] == 2 and r[RGOWN] == 'ours'

    def after_blind(self):
        mut = self.mut
        if self.rev == 4 or 'popoff_split' in mut or 'off_split' in mut: return 'D_POP'
        if 'gate_split' in mut: return 'D_POg'
        return 'D_PO'

    # ---------------------------------------------------------------- exceptions
    def flag(self, ths, sh, c, ev):
        if c not in sh[GHOST_][2] and c not in self.a0(ths, sh, False): ev.append('FALSEFLAG')
        return cset(sh, c, FLAG, True)

    def unwind(self, ths, sh, pk, k, fr, ev):
        """An exception at fr: inside _run's try -> the finally; else the frame dies (with-exit releases L)."""
        kind, slot, core, pc, cs, r, uid = fr
        if kind in ('open', 'aopen', 'lockopen', 'close') and r[INTRY]:
            f2 = (kind, slot, core, 'F_D', (), setr(setr(setr(r, INTRY, False), TXN, None), TOK, None), uid)
            return (self.settop(ths, k, f2), sh, pk)
        sh2 = sh
        if r[HOLDL] and sh[L_] == k: sh2 = sset(sh2, L_, None)
        return (self.poptop(ths, k), sh2, pk)

    def raise_(self, ths, sh, pk, k, fr, ev):
        ev.append('VALUEERROR')
        ths2, sh2, pk2 = self.unwind(ths, sh, pk, k, fr, ev)
        return [(ths2, sh2, pk2, ev)]

    def gse(self, ths, sh, pk, k, fr, ev):
        """A GateSpecError (REENTRANT or MACHINERY_BUSY) out of _locked: exit's X5 catches it and goes on to X8;
        anywhere else it propagates (the program ends)."""
        kind, slot, core, pc, cs, r, uid = fr
        if pc == 'X5A':
            f2 = (kind, slot, core, 'X8', (), r, uid)
            return [(self.settop(ths, k, f2), cset(sh, core, NOTE, 'busy'), pk, ev)]
        ths2, sh2, pk2 = self.unwind(ths, sh, pk, k, fr, ev)
        return [(ths2, sh2, pk2, ev)]

    def timeout(self, ths, sh, pk, k):
        fr = self.top(ths, k)
        if fr is None: return []
        pc = fr[PC]
        if pc in ('X5A', 'E4A', 'RA') and not BOUNDED['tx']: return []
        if pc == 'C_WT' and not BOUNDED['open']: return []
        if pc in ('X5A', 'E4A', 'RA'):
            if not (sh[G_] is not None and self.alive(ths, sh[G_], TXN) and sh[G_][0][0] != k): return []
            ev = ['BUSY_TX']
            return self.gse(ths, sh, pk, k, fr, ev)
        if pc == 'C_WT':
            if not self.step(ths, sh, pk, k) == []: return []
            ev = ['BUSY_OPEN']
            ths2, sh2, pk2 = self.unwind(ths, sh, pk, k, fr, ev)
            return [(ths2, sh2, pk2, ev)]
        return []

    def fault(self, ths, sh, pk, k):
        fr = self.top(ths, k)
        if fr is None: return None
        ths2, sh2, pk2 = self.unwind(ths, sh, pk, k, fr, [])
        return ths2, sh2, pk2

    # ---------------------------------------------------------------- adversarial moves
    def interrupts(self, ths, sh, pk, k):
        out = []
        cfg = self.cfg
        if cfg.intr_on is not None and k not in cfg.intr_on: return out
        if self.top(ths, k) is None: return out
        for i, (kind, core, slot) in enumerate(cfg.intr):
            if i in sh[USED_]: continue
            if kind == 'lock' and self.holds_lock(ths, k): continue    # a self-deadlock untraced too: not generated
            ths2 = self.push(ths, k, kind, core, slot)
            out.append((ths2, sset(sh, USED_, sh[USED_] | {i}), pk))
        return out

    def externals(self, ths, sh, pk):
        out = []
        tool = sh[TOOL_]; ext = sh[GHOST_][0]; xl = sh[GHOST_][4]
        for kind in self.ext_kinds:
            if xl.count(kind) >= self.cfg.xrep: continue  # each kind at most xrep times per run (1 unless stated)
            sh2 = None
            if kind == 'clear' and tool == 'ours' and sh[S_]: sh2 = sset(sh, S_, False)
            elif kind == 'set' and tool == 'ours' and not sh[S_]:
                sh2 = sset(sh, S_, True)
                m = self.a0(ths, sh, False)              # the blind interval ends unobserved: MASKED
                if m: sh2 = gset(sh2, 3, sh[GHOST_][3] | m)
            elif kind == 'free' and tool in ('ours', 'other'): sh2 = sset(sh, TOOL_, 'freed')
            elif kind == 'take' and tool == 'freed': sh2 = sset(sset(sh, TOOL_, 'other'), CB_, ('F', 'F'))
            elif kind == 'cbrep' and tool == 'ours' and sh[CB_][1] == 'S': sh2 = sset(sh, CB_, (sh[CB_][0], 'F'))
            elif kind == 'cbrep0' and tool == 'ours' and sh[CB_][0] == 'S': sh2 = sset(sh, CB_, ('F', sh[CB_][1]))
            elif kind == 'lclr' and tool == 'ours' and sh[MINT_][0] and sh[MINT_][2]:
                m = sh[MINT_]; sh2 = sset(sh, MINT_, (m[0], m[1], False, m[3]))
            if sh2 is not None:
                sh2 = gset(sh2, 4, tuple(sorted(xl + (kind,))))
                out.append((ths, gset(sh2, 0, ext | {kind}), pk))
        return out

    def switches(self, ths, sh, pk, k):
        gls, act, ser = ths[k]
        out = []
        for gi, st in enumerate(gls):
            if gi != act and st: out.append((ths[:k] + ((gls, gi, ser),) + ths[k + 1:], sh, pk))
        return out

    def resumes(self, ths, sh, pk, k):
        if not pk or not self.idle(ths, k): return []
        out = []
        for f in pk:
            out.append((self.pushframe(ths, k, f), sh, pk - {f}))
        return out

    # ---------------------------------------------------------------- repair: finish every trace, then reconcile
    def repair(self, ths, sh):
        extra = []
        for c in range(self.cfg.ncores):
            cr = sh[CORES_][c]
            if cr[ACT] and cr[EXI] is None and not cr[EXD]: extra.append(('exit', c))
        extra.append(('rec', None))
        k = len(ths)
        for kind, c in extra:
            t2 = ths + (((( self.newframe(kind, c, None, (k, 0, 0)),),), 0, 1),)
            n = 0; pk = frozenset()
            while self.top(t2, k) is not None:
                succ = self.step(t2, sh, pk, k)
                if not succ:                              # blocked: a stale mutex owner is dead, so this is a bug
                    return sh, 'REPAIR_BLOCKED'
                t2, sh, pk, _ = succ[0]; n += 1
                if n > 5000: return sh, 'REPAIR_LOOP'
        return sh, None

# ------------------------------------------------------------------ exploration
BOUNDED = {'open': True, 'tx': True}             # the 'hang' mode turns a busy bound off, to show HANG is real
KEYS = ('U1', 'A0', 'STALE', 'FALSEFLAG', 'CLOBBER', 'P8', 'HANG', 'LOSTNOTE', 'END', 'REPAIR', 'VALUEERROR',
        'CYC_OPEN', 'REGMULTI', 'REGSILENT', 'CYC_TX', 'BUSY_OPEN', 'BUSY_TX', 'REENT', 'LOST', 'MASKED', 'REGCLOB',
        'STALE_rev4')
VIOLATIONS = ('U1', 'A0', 'STALE', 'FALSEFLAG', 'CLOBBER', 'P8', 'HANG', 'LOSTNOTE', 'END', 'REPAIR', 'VALUEERROR',
              'CYC_OPEN', 'REGMULTI', 'REGSILENT')

def explore(cfg, rev, budget, mut=frozenset(), limit=30_000_000):
    F, I, X, Wsw = budget
    m = Model(cfg, rev, mut)
    ths0, sh0, pk0 = m.initial()
    start = (ths0, sh0, pk0, F, I, X, Wsw)
    seen = set(); stack = [start]
    res = {k: 0 for k in KEYS}; res['states'] = 0; res['ends'] = 0
    while stack:
        st = stack.pop()
        h = hash(st)
        if h in seen: continue
        seen.add(h); res['states'] += 1
        if res['states'] > limit: res['TRUNCATED'] = 1; break
        ths, sh, pk, f, i, x, w = st
        ff = f == F
        ext = sh[GHOST_][0]
        # state properties
        a0c = m.a0(ths, sh, True, pk)
        if a0c and not ext: res['A0'] += 1
        a0raw = m.a0(ths, sh, False)
        if a0raw - sh[GHOST_][2]:
            sh = gset(sh, 2, sh[GHOST_][2] | a0raw)      # ghost history (not a new state: recorded in place)
        if sh[S_] and not sh[A_] and not (ext & {'set', 'free', 'take'}):
            res['STALE' if rev >= 5 else 'STALE_rev4'] += 1
        nth = len(ths)
        live = [k for k in range(nth) if m.top(ths, k) is not None]
        if not live and not pk:
            res['ends'] += 1
            end_checks(m, ths, sh, ff and not ext, res)
            continue
        progress = []
        for k in range(nth):
            for (t2, s2, p2, ev) in m.step(ths, sh, pk, k):
                progress.append((t2, s2, p2, ev))
            for (t2, s2, p2) in m.resumes(ths, sh, pk, k):
                progress.append((t2, s2, p2, ()))
        timeouts = []
        for k in live:
            timeouts += m.timeout(ths, sh, pk, k)
        if not progress:
            if timeouts:
                blocked = [m.top(ths, k)[PC] for k in live]
                if 'C_WT' in blocked: res['CYC_OPEN'] += 1
                else: res['CYC_TX'] += 1
            else:
                res['HANG'] += 1
        for (t2, s2, p2, ev) in progress + timeouts:
            for e in ev:
                if e in res: res[e] += 1
            stack.append((t2, s2, p2, f, i, x, w))
        if f > 0:
            for k in live:
                r = m.fault(ths, sh, pk, k)
                if r: stack.append((r[0], r[1], r[2], f - 1, i, x, w))
        if i > 0:
            for k in live:
                for (t2, s2, p2) in m.interrupts(ths, sh, pk, k): stack.append((t2, s2, p2, f, i - 1, x, w))
        if x > 0:
            for (t2, s2, p2) in m.externals(ths, sh, pk): stack.append((t2, s2, p2, f, i, x - 1, w))
        if w > 0:
            for k in live:
                for (t2, s2, p2) in m.switches(ths, sh, pk, k): stack.append((t2, s2, p2, f, i, x, w - 1))
    return res

def end_checks(m, ths, sh, clean, res):
    S, A, CLR, G, L = sh[S_], sh[A_], sh[CLR_], sh[G_], sh[L_]
    ops = sh[OPS_]
    if clean:
        bad = (A or S or CLR or (G is not None and m.alive(ths, G, TXN)) or L is not None
               or any(op[0] and op[2] is None for op in ops) or any(c[FLAG] for c in sh[CORES_]))
        if bad: res['END'] += 1
    sh2, err = m.repair(ths, sh)
    if err: res['REPAIR'] += 1; return
    if sh2[A_] or sh2[CLR_] or (sh2[S_] and sh2[TOOL_] == 'ours') or sh2[MINT_][0] or sh2[MINT_][1]:
        res['REPAIR'] += 1
    for c in sh2[GHOST_][5]:                           # revision 6: a registration exchange on another's id
        note = sh2[CORES_][c][NOTE]
        if note is not None and not note: res['REGSILENT'] += 1
    lost = sh2[GHOST_][1]; masked = sh2[GHOST_][3]
    for c in lost:
        res['LOST'] += 1
        note = sh2[CORES_][c][NOTE]
        if note is None: continue                        # the record is not readable (exit began and faulted)
        if not note:
            if c in masked: res['MASKED'] += 1
            else: res['LOSTNOTE'] += 1

# ------------------------------------------------------------------ configurations
X, Y, Z = 0, 1, 2
def P(kind, core, slot=None): return (kind, core, slot)
CONFIGS = [
    # ---- rev4's pairs and triples (cross-thread), now with E4 / retire / reclaim in the transactions
    Cfg('open(X) || exit(X)', [[P('open', X, 0)], [P('exit', X)]], 1, 'open/exit, close/exit: same tracer'),
    Cfg('close(X) || exit(X)', [[P('close', X, 0)], [P('exit', X)]], 1, 'close/exit same tracer'),
    Cfg('open(X) || open(X)', [[P('open', X, 0)], [P('open', X, 1)]], 1, 'open/open, open/close, close/close'),
    Cfg('open(X) || open(Y)', [[P('open', X, 0)], [P('open', Y, 1)]], 2, 'two tracers'),
    Cfg('open(Y) || exit(X)', [[P('open', Y, 0)], [P('exit', X)]], 2, 'open/exit of another tracer (retire, reconcile)'),
    Cfg('exit(X) || exit(X)', [[P('exit', X)], [P('exit', X)]], 1, 'exit/exit same tracer'),
    Cfg('exit(X) || exit(Y)', [[P('exit', X)], [P('exit', Y)]], 2, 'exit/exit two tracers'),
    Cfg('rec || open(X), X facade dead', [[P('rec', None)], [P('open', X, 0)]], 1, 'prune vs open/close', facade_dead=(X,)),
    Cfg('rec || open(Y)', [[P('rec', None)], [P('open', Y, 0)]], 2, 'reconcile vs open/close'),
    Cfg('rec || exit(X)', [[P('rec', None)], [P('exit', X)]], 1, 'reconcile/exit'),
    Cfg('enter(X) || exit(Y)', [[P('enter', X)], [P('exit', Y)]], 2, 'E4 (mint join) vs retire', not_entered=(X,)),
    Cfg('enter(X) || open(Y)', [[P('enter', X)], [P('open', Y, 0)]], 2, 'E4 vs a section', not_entered=(X,)),
    Cfg('enter(X) || enter(X)', [[P('enter', X)], [P('enter', X)]], 1, 'double enter (REENTRY)', not_entered=(X,)),
    Cfg('open(X) || exit(X) || rec', [[P('open', X, 0)], [P('exit', X)], [P('rec', None)]], 1, 'exit faulted, prune, open', faults=(0, 1)),
    Cfg('open(X) || open(X) || exit(Y)', [[P('open', X, 0)], [P('open', X, 1)], [P('exit', Y)]], 2, 'two sections and a retire', faults=(0, 1)),
    Cfg('open(X) || open(X) || exit(X)', [[P('open', X, 0)], [P('open', X, 1)], [P('exit', X)]], 1, 'open/exit with a second section', faults=(0, 1)),
    Cfg('open(X) || exit(X) || exit(X)', [[P('open', X, 0)], [P('exit', X)], [P('exit', X)]], 1, 'exit/exit same tracer with a section', faults=(0, 1)),
    # ---- same-thread re-entry (interrupts at every step boundary)
    Cfg('close(X)+[open(Y)] || open(Y)', [[P('close', X, 0)], [P('open', Y, 1)]], 2, 'a section run inside a close (finalizer / signal handler)',
        intr=[P('open', Y, 2)], intr_on=(0,), I=1),
    Cfg('R19: close(X)+[aopen(Y)] || idle', [[P('close', X, 0)], []], 2, 'a run_async section opened inside a close, left suspended, resumed (same thread or hop)',
        intr=[P('aopen', Y, 1)], intr_on=(0,), I=1),
    Cfg('R19+mask: close(X)+[aopen(Y)] || open(Z)', [[P('close', X, 0)], [P('open', Z, 2)]], 3, 'R19 with another opener that re-sets the event (c2b)',
        intr=[P('aopen', Y, 1)], intr_on=(0,), I=1, faults=(0,)),
    Cfg('c8: close(X)+[open(Y)] || close(X)+[open(Y)]', [[P('close', X, 0)], [P('close', X, 1)]], 2, 'sections opened inside two closes at once (nested wait cycle)',
        intr=[P('open', Y, 2), P('open', Y, 3)], I=2, faults=(0,)),
    Cfg('open(X)+[exit(X)]', [[P('open', X, 0)]], 1, 'the tracer exited from inside its own open (finalizer)',
        intr=[P('exit', X)], I=1),
    Cfg('exit(X)+[rec] || open(Y)', [[P('exit', X)], [P('open', Y, 0)]], 2, 'a transaction inside a transaction (REENTRANT)',
        intr=[P('rec', None)], intr_on=(0,), I=1),
    Cfg('aopen(X) || exit(X) || idle', [[P('aopen', X, 0)], [P('exit', X)], []], 1, 'run_async suspended across its own exit, resumed on another thread'),
    # ---- user code that blocks inside a window
    Cfg('c3: with L: open(X) || close(Y)+[lock]', [[P('lockopen', X, 0)], [P('close', Y, 1)]], 2, 'a finalizer in a close needs a lock the opener holds',
        intr=[P('lock', None, None)], intr_on=(1,), I=1),
    Cfg('with L: exit(X) || exit(Y)+[lock]', [[P('lockexit', X)], [P('exit', Y)]], 2, 'an audit hook in a transaction needs a lock an exiting thread holds',
        intr=[P('lock', None, None)], intr_on=(1,), I=1, faults=(0,)),
    Cfg('with L: open(X) || open(Y)+[lock]', [[P('lockopen', X, 0)], [P('open', Y, 1)]], 2, 'blocking user code at every point of an open',
        intr=[P('lock', None, None)], intr_on=(1,), I=1, faults=(0,)),
    # ---- external parties
    Cfg('ext: open(X) || open(Y)', [[P('open', X, 0)], [P('open', Y, 1)]], 2, 'outside clear/set/free/take between any steps',
        ext=('clear', 'set', 'free', 'take'), X=2, faults=(0,)),
    Cfg('ext: open(X) || exit(X)', [[P('open', X, 0)], [P('exit', X)]], 1, 'outside party vs open/exit', ext=('clear', 'set', 'free', 'take'), X=2, faults=(0,)),
    Cfg('ext: close(X) || rec', [[P('close', X, 0)], [P('rec', None)]], 1, 'free, reclaim, take races', ext=('free', 'take'), X=2),
    Cfg('ext: enter(X) || open(Y)', [[P('enter', X)], [P('open', Y, 0)]], 2, 'E4 with an outside free/take', ext=('free', 'take', 'clear'), X=2, not_entered=(X,), faults=(0,)),
    # ---- revision 6: callback registration with audit hooks inside (B1), rebinding (N1), combinations (M2)
    Cfg('reg: exit(X) + outside free/take', [[P('exit', X)]], 1, 'X5 re-registration with the id freed and taken inside it',
        ext=('free', 'take'), X=2, faults=(0, 1)),
    Cfg('reg: open(Y) || exit(X) + free/take', [[P('open', Y, 0)], [P('exit', X)]], 2, 'a live trace while X5 registers',
        ext=('free', 'take'), X=2, faults=(0,)),
    Cfg('reg: first enter(X) + free/take', [[P('enter', X)]], 1, 'first acquisition: take, register, rebind to id 3',
        ext=('free', 'take'), X=2, not_entered=(X,), faults=(0, 1), fresh=True),
    Cfg('reg: rec || open(X) + free/take/free', [[P('rec', None)], [P('open', X, 0)]], 1, 'reclaim with a repeated free (free, reclaim, free)',
        ext=('free', 'take'), X=3, xrep=2, faults=(0,)),
    Cfg('rebind: enter(X) || open(Y) + take', [[P('enter', X)], [P('open', Y, 0)]], 2, 'X joins Y\'s mint after another tool took the id',
        ext=('free', 'take'), X=2, not_entered=(X,), faults=(0,)),
    Cfg('cb/local: open(X) || exit(X)', [[P('open', X, 0)], [P('exit', X)]], 1, 'an outside party replaces a callback or clears local events',
        ext=('cbrep', 'lclr'), X=1, faults=(0,)),
    Cfg('ext+re: close(X)+[open(Y)] || open(Y)', [[P('close', X, 0)], [P('open', Y, 1)]], 2, 'outside parties and a section run inside a close',
        intr=[P('open', Y, 2)], intr_on=(0,), I=1, ext=('clear', 'set', 'free', 'take'), X=1, faults=(0,)),
    Cfg('ext+re: exit(X)+[rec] || open(Y)', [[P('exit', X)], [P('open', Y, 0)]], 2, 'outside parties and a transaction inside a transaction',
        intr=[P('rec', None)], intr_on=(0,), I=1, ext=('clear', 'free', 'take'), X=1, faults=(0,)),
    Cfg('ext+greenlet: [close(X), open(X)] || open(Y)', [[P('close', X, 0), P('open', X, 1)], [P('open', Y, 2)]], 2, 'outside parties and a switch inside a close',
        Wsw=2, ext=('clear', 'set', 'free', 'take'), X=1, faults=(0,)),
    Cfg('ext+greenlet: [exit(X), rec] || open(X)', [[P('exit', X), P('rec', None)], [P('open', X, 0)]], 1, 'outside parties and a stolen mutex',
        Wsw=2, ext=('clear', 'free', 'take'), X=1, faults=(0,)),
    Cfg('ext+async: aopen(X) || exit(X) || idle', [[P('aopen', X, 0)], [P('exit', X)], []], 1, 'outside parties and a suspended run_async section',
        ext=('clear', 'set', 'free', 'take'), X=1, faults=(0,)),
    # ---- greenlets
    Cfg('greenlet: [close(X), open(X)] || open(Y)', [[P('close', X, 0), P('open', X, 1)], [P('open', Y, 2)]], 2, 'a switch inside a close',
        Wsw=2, faults=(0,)),
    Cfg('greenlet: [exit(X), rec] || open(X)', [[P('exit', X), P('rec', None)], [P('open', X, 0)]], 1, 'a switch inside a transaction (the mutex is stolen)',
        Wsw=2, faults=(0,)),
]

CONFIGS7 = [   # revision 7 (M5): outside callback/local-event changes with two cores; registrations with a second live core
    Cfg('cb2: open(Y) || exit(X) [cbrep]', [[P('open', Y, 0)], [P('exit', X)]], 2, 'critic7 c2: Y loses a call, X exits first',
        ext=('cbrep',), X=1, faults=(0,)),
    Cfg('cb2: open(Y) || exit(X) [cbrep0]', [[P('open', Y, 0)], [P('exit', X)]], 2, 'the entry callback replaced',
        ext=('cbrep0',), X=1, faults=(0,)),
    Cfg('cb2: open(Y) || exit(X) [lclr]', [[P('open', Y, 0)], [P('exit', X)]], 2, 'local events of the shared mint cleared',
        ext=('lclr',), X=1, faults=(0,)),
    Cfg('cb2: open(Y) || exit(X) [all, X2]', [[P('open', Y, 0)], [P('exit', X)]], 2, 'two outside changes of any kind',
        ext=('cbrep', 'cbrep0', 'lclr'), X=2, faults=(0,)),
    Cfg('cb2: open(X) || open(Y) || exit(Y) [cbrep]', [[P('open', X, 0)], [P('open', Y, 1)], [P('exit', Y)]], 2, 'both lose, Y exits first',
        ext=('cbrep', 'cbrep0'), X=1, faults=(0,)),
    Cfg('cb2: open(Y) || exit(X) [cbrep, F1]', [[P('open', Y, 0)], [P('exit', X)]], 2, 'a fault anywhere, X5 included',
        ext=('cbrep', 'lclr'), X=1, faults=(1,)),
    Cfg('cb2+greenlet: [exit(X), exit(Z)] || open(Y) [cbrep]', [[P('exit', X), P('exit', Z)], [P('open', Y, 0)]], 3,
        'a switch inside X5 registration hands the mutex to another exit', Wsw=2, ext=('cbrep', 'cbrep0'), X=1, faults=(0,)),
    Cfg('cb2+re: exit(X)+[exit(Z)] || open(Y) [cbrep]', [[P('exit', X)], [P('open', Y, 0)]], 3,
        'an exit re-entered inside an exit (REENTRANT), with a replaced callback', intr=[P('exit', Z)], intr_on=(0,), I=1,
        ext=('cbrep',), X=1, faults=(0,)),
    Cfg('rebind2: enter(X) || open(Y) + take [other id has styxx leftovers]', [[P('enter', X)], [P('open', Y, 0)]], 2,
        'X137h: a rebinding onto an id that still carries styxx callbacks (no in-call count)',
        ext=('free', 'take'), X=2, not_entered=(X,), faults=(0,), oth_left=True),
    Cfg('reg2: rec || open(Y) + free/take', [[P('rec', None)], [P('open', Y, 0)]], 2, 'a reclaim with a second live core',
        ext=('free', 'take'), X=2, faults=(0, 1)),
    Cfg('reg2: rec || open(Y) + free/free', [[P('rec', None)], [P('open', Y, 0)]], 2, 'a reclaim split with owner None',
        ext=('free',), X=2, xrep=2, faults=(0, 1)),
    Cfg('reg2: enter(X) || open(Y) + free x3', [[P('enter', X)], [P('open', Y, 0)]], 2, 'E4: both reclaims split with owner None, then the same-id re-take',
        ext=('free',), X=3, xrep=3, not_entered=(X,), faults=(0,)),
    Cfg('reg2: enter(X) || open(Y) + free/take, F1', [[P('enter', X)], [P('open', Y, 0)]], 2, 'E4 with a raising hook and a second live core',
        ext=('free', 'take'), X=2, not_entered=(X,), faults=(1,)),
    Cfg('reg2: enter(X) || exit(Y) + free/take/cbrep', [[P('enter', X)], [P('exit', Y)]], 2, 'E4 registration while another trace exits',
        ext=('free', 'take', 'cbrep'), X=2, not_entered=(X,), faults=(0,)),
]
CONFIGS_ALL = CONFIGS + CONFIGS7

PAIRS2 = ('open(X) || exit(X)', 'close(X) || exit(X)', 'open(X) || open(X)', 'open(X) || open(Y)', 'open(Y) || exit(X)',
          'exit(X) || exit(X)', 'exit(X) || exit(Y)', 'rec || open(X), X facade dead', 'rec || open(Y)', 'rec || exit(X)',
          'enter(X) || exit(Y)', 'enter(X) || open(Y)', 'enter(X) || enter(X)')
def budgets(cfg, rev):
    out = []
    faults = (0, 1, 2) if cfg.name in PAIRS2 else cfg.faults
    for f in faults:
        out.append((f, cfg.I, cfg.X, cfg.Wsw))
    return out

def fmt(r):
    bad = [('%s=%d' % (k, r[k])) for k in VIOLATIONS if r.get(k)]
    info = [('%s=%d' % (k, r[k])) for k in ('LOST', 'MASKED', 'REGCLOB', 'CYC_TX', 'BUSY_TX', 'BUSY_OPEN', 'REENT', 'STALE_rev4') if r.get(k)]
    s = ', '.join(bad) if bad else 'ok'
    if info: s += '  [' + ', '.join(info) + ']'
    if r.get('TRUNCATED'): s += ' TRUNCATED'
    return s

if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'main'
    if which == 'main':
        sel = sys.argv[2:]
        for cfg in CONFIGS_ALL:
            if sel and not any(s in cfg.name for s in sel): continue
            for rev in (6, 7):
                for b in budgets(cfg, rev):
                    t0 = time.time()
                    r = explore(cfg, rev, b)
                    print('%-46s rev%d F%d I%d X%d W%d %9d states %6d ends  %s  (%.0fs)' % (
                        cfg.name, rev, b[0], b[1], b[2], b[3], r['states'], r['ends'], fmt(r), time.time() - t0), flush=True)
    elif which == 'only':                            # main, restricted: only REV revisions, named configurations
        revs = tuple(int(x) for x in sys.argv[2].split(',')); sel = sys.argv[3:]
        for cfg in CONFIGS_ALL:
            if not any(s == cfg.name for s in sel): continue
            for rev in revs:
                for b in budgets(cfg, rev):
                    t0 = time.time()
                    r = explore(cfg, rev, b)
                    print('%-46s rev%d F%d I%d X%d W%d %9d states %6d ends  %s  (%.0fs)' % (
                        cfg.name, rev, b[0], b[1], b[2], b[3], r['states'], r['ends'], fmt(r), time.time() - t0), flush=True)
    elif which == 'hang':                            # the same model with a wait's busy bound removed
        names = ('c8:', 'c3:', 'with L: exit', 'with L: open', 'close(X)+[open(Y)] || open(Y)', 'greenlet:', 'ext+greenlet:', 'ext+re:')
        for cfg in CONFIGS_ALL:
            if not any(cfg.name.startswith(n) for n in names): continue
            for rev in (6, 7):
                for bounded in (('open',), ('tx',)):
                    BOUNDED['open'] = 'open' not in bounded; BOUNDED['tx'] = 'tx' not in bounded
                    if rev >= 5 and bounded == ('open',): continue   # revision 5 has no opener wait
                    b = (0, cfg.I, cfg.X, cfg.Wsw)
                    r = explore(cfg, rev, b)
                    print('%-46s rev%d %-18s %9d states  %s' % (cfg.name, rev, 'no %s bound' % bounded[0], r['states'], fmt(r)), flush=True)
            BOUNDED['open'] = BOUNDED['tx'] = True
    elif which == 'mutants':
        MUTS = ['off_split', 'popoff_split', 'on_ungated_own', 'on_no_capture', 'on_capture_split', 'on_capture_nogate',
                'on_before_store', 'no_on', 'blind_anchor_first', 'blind_no_armed', 'blind_no_anchor', 'no_rec_off',
                'gate_split', 'detach_nulls', 'no_recheck', 'no_fin_test', 'no_exiting_test', 'no_anchor_prune',
                'take_split', 'ensure_nocount', 'prune_credit_stop', 'reg_rev5', 'rebind_count_none', 'rebind_no_local',
                'blind_read_gated', 'ensure_nocount+blind_read_gated', 'cbrep_nocount', 'count_after_register', 'retake_nocount',
                'retake_nocount+blind_read_gated']
        sel = sys.argv[2:]
        if sel: MUTS = sel
        for mu in MUTS:                              # revision 7: every configuration, CONFIGS7 included
            found = []
            for cfg in CONFIGS_ALL:
                for b in budgets(cfg, 7):
                    r = explore(cfg, 7, b, frozenset(mu.split('+')))
                    f = fmt(r)
                    if not f.startswith('ok'):
                        found.append('%s F%d: %s' % (cfg.name, b[0], f)); break
                if len(found) >= 3: break
            print('%-20s %s' % (mu, (' | '.join(found)) if found else 'NOT DETECTED by any configuration'), flush=True)

# ------------------------------------------------------------------ counterexample paths (debugging aid)
def find_path(cfg, rev, budget, want, mut=frozenset(), limit=5_000_000):
    """BFS with parent links; returns the move list to the first state/transition/end that raises `want`."""
    from collections import deque
    F, I, X, Wsw = budget
    m = Model(cfg, rev, mut)
    ths0, sh0, pk0 = m.initial()
    start = (ths0, sh0, pk0, F, I, X, Wsw)
    parent = {hash(start): (None, 'start')}
    q = deque([start]); n = 0
    def path(h):
        out = []
        while h is not None:
            ph, mv = parent[h]; out.append(mv); h = ph
        return list(reversed(out))
    while q:
        st = q.popleft(); n += 1
        if n > limit: return None
        h = hash(st)
        ths, sh, pk, f, i, x, w = st
        ext = sh[GHOST_][0]
        a0raw = m.a0(ths, sh, False)
        if a0raw - sh[GHOST_][2]: sh = gset(sh, 2, sh[GHOST_][2] | a0raw)
        live = [k for k in range(len(ths)) if m.top(ths, k) is not None]
        if not live and not pk:
            res = {k: 0 for k in KEYS}
            end_checks(m, ths, sh, f == F and not ext, res)
            if res.get(want): return path(h) + ['END: ' + str({k: v for k, v in res.items() if v})]
            continue
        moves = []
        for k in range(len(ths)):
            fr = m.top(ths, k)
            for (t2, s2, p2, ev) in m.step(ths, sh, pk, k):
                moves.append(('T%d %s%s' % (k, fr[PC] if fr else '?', (' ' + ','.join(ev)) if ev else ''), (t2, s2, p2, f, i, x, w), ev))
            for (t2, s2, p2) in m.resumes(ths, sh, pk, k): moves.append(('T%d resume' % k, (t2, s2, p2, f, i, x, w), ()))
            for (t2, s2, p2, ev) in m.timeout(ths, sh, pk, k): moves.append(('T%d timeout' % k, (t2, s2, p2, f, i, x, w), ev))
        if f > 0:
            for k in live:
                r = m.fault(ths, sh, pk, k)
                if r: moves.append(('T%d FAULT at %s' % (k, m.top(ths, k)[PC]), (r[0], r[1], r[2], f - 1, i, x, w), ()))
        if i > 0:
            for k in live:
                for (t2, s2, p2) in m.interrupts(ths, sh, pk, k): moves.append(('T%d INTERRUPT at %s' % (k, m.top(ths, k)[PC]), (t2, s2, p2, f, i - 1, x, w), ()))
        if x > 0:
            for (t2, s2, p2) in m.externals(ths, sh, pk):
                moves.append(('EXT %s' % sorted(s2[GHOST_][0] - ext), (t2, s2, p2, f, i, x - 1, w), ()))
        if w > 0:
            for k in live:
                for (t2, s2, p2) in m.switches(ths, sh, pk, k): moves.append(('T%d SWITCH' % k, (t2, s2, p2, f, i, x, w - 1), ()))
        for mv, st2, ev in moves:
            h2 = hash(st2)
            if h2 in parent: continue
            parent[h2] = (h, mv + ('  [S=%d A=%s tool=%s]' % (st2[1][S_], sorted(st2[1][A_]), st2[1][TOOL_])))
            if want in ev: return path(h2)
            q.append(st2)
    return None
