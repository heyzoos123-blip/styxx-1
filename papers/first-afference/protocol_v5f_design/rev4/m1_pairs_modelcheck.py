# Exhaustive interleaving check of the open/commit/close/exit/reconcile protocol, revision 3 against revision 4,
# over every pair (and the relevant triples) of concurrent transitions. Revision 3's m1 ran two sections and a
# retire; this one adds exit (X1-X8) of the SAME tracer as a section, a second exit, and a reconciliation that
# prunes a dead core, so the races the last three critiques found (retire vs open, open vs its own exit, close vs
# its own exit) are all inside the enumeration.
#
# Abstract state: S (styxx's global PY_UNWIND is set), A (registered anchors, as (key, opening) pairs), CLR (announced
# clearers, revision 4), the robust mutex G, per-core marks and credit, and per-opening (appended, frame, fin, armed).
# Every single C operation (dict store / pop / get / setdefault, one sys.monitoring call, one attribute store) is its
# own step, and a step boundary lies between any two of them. That is finer than CPython's eval-breaker points, so it
# is the granularity at which any instrument that runs Python code between two machinery bytecodes (the id-5
# injector, a profiler, a CALL/INSTRUCTION/opcode tool) can interleave another thread. Revision 3's one-line
# test-and-clear is one step in 'rev3' (its claim: nothing can run inside it) and two steps in 'rev3-split'.
#
# Threads (programs mirror the spec's pseudocode step by step; see OPENER/DETACH/UNWIND_OFF/EXIT/RECONCILE below):
#   open(c)   one whole section of core c: _open's step 2 and append, then _run's try: _commit, one hit of a declared
#             target in the body, then the finally's _detach and (revision 4) the owner's release of o.frame;
#   close(c)  the same section starting armed, in its body (to isolate close-vs-X);
#   exit(c)   X1 claim, X2 credit stop, X3 detach of every appended opening, X5 transaction under the mutex
#             (reconciliation, ending with _unwind_off), X8;
#   rec       another tracer's transaction: the mutex, then a reconciliation (prune of dead cores; revision 4 also
#             sweeps anchors of dead cores and dead clearer announcements), ending with _unwind_off.
# Faults: 0, 1 or 2 injected exceptions, each at any step boundary of any thread. Inside _run's try a fault jumps to
# the finally; anywhere else it ends that thread (an exit faulted after X1 leaves a dead 'exiting' token, so its core
# is prunable). A thread blocked in a wait can also be faulted.
# Visited states are stored as 64-bit hashes (a collision could hide a state: probability about n^2/2^65).
# Properties checked:
#   U1    no hit runs with S clear while its core is still crediting (X2 / prune not yet run);
#   P8    step 8: no body runs whose opening was already claimed by a detacher (exit's X3, a prune), or whose core's
#         exit had already begun (X1), when the opener stored its anchor: such an open refuses TRACE_INACTIVE;
#   A0    in every reachable state: an armed opening whose anchor is registered and whose core is crediting has S set;
#   HANG  no reachable state where live threads exist and none can step;
#   END (fault-free end states): A empty, S clear, CLR empty, mutex free, every appended opening finalised, and no
#         UNWIND_LOST flag (no party clears S from outside in this model, so every flag is false);
#   REPAIR (faulted end states): after the owning trace's exit (for cores whose exit never ran) and one more
#         reconciliation, all fault-free, A, S and CLR are empty; and no UNWIND_LOST flag anywhere (I6 without the
#         instrument exception).
import sys, time

SPLIT = False
MUT = set()
REV = 4

# registers
INTRY, OUT, N, TXN, TOK, W, ONL, DFR, DARM, DS, DOID, DTAG, XL, XI, PL, PI, SL, SI, HIT, LATE = range(20)
NREG = 20

def setr(regs, i, v): return regs[:i] + (v,) + regs[i + 1:]

class Cfg:
    def __init__(self, name, threads, cores, pairs, facade_dead=()):
        self.name, self.threads, self.ncores, self.pairs, self.facade_dead = name, threads, cores, pairs, facade_dead

# shared: (S, A, CLR, G, cores, ops); core = (exiting_tid|None, exited, crediting, facade_dead, flag)
# op = (appended, frame, fin, armed)
def sh_set(sh, i, v): return sh[:i] + (v,) + sh[i + 1:]
def core_set(sh, c, j, v):
    cs = sh[4]; cr = cs[c]; cr = cr[:j] + (v,) + cr[j + 1:]
    return sh_set(sh, 4, cs[:c] + (cr,) + cs[c + 1:])
def op_set(sh, o, j, v):
    os_ = sh[5]; r = os_[o]; r = r[:j] + (v,) + r[j + 1:]
    return sh_set(sh, 5, os_[:o] + (r,) + os_[o + 1:])

class Model:
    def __init__(self, cfg, rev, split, mut):
        self.cfg, self.rev, self.split, self.mut = cfg, rev, split, mut
        self.kinds = [t[0] for t in cfg.threads]
        self.core_of_thread = [t[1] for t in cfg.threads]
        # each open/close thread owns one opening, numbered by thread index
        self.op_core = {}
        for k, t in enumerate(cfg.threads):
            if t[0] in ('open', 'close'): self.op_core[k] = t[1]

    # ---- liveness ----
    def tok_alive(self, ths, tok):
        th = ths[tok[0]]
        return th[3] == 'run' and th[2][TOK] == tok
    def g_alive(self, ths, g):
        th = ths[g[0]]
        return th[3] == 'run' and th[2][TXN] == g
    def core_dead(self, ths, sh, c):
        ex, exited, cred, fdead, flag = sh[4][c]
        if fdead or exited: return True
        if ex is not None:
            th = ths[ex]
            return th[3] != 'run'
        return False
    def appended(self, sh, c):
        return tuple(o for o in sorted(self.op_core) if self.op_core[o] == c and sh[5][o][0])

    # ---- initial ----
    def initial(self):
        ncores = self.cfg.ncores
        cores = tuple((None, False, True, c in self.cfg.facade_dead, False) for c in range(ncores))
        ops = [(False, None, None, False)] * len(self.cfg.threads)
        S = False; A = frozenset()
        ths = []
        for k, t in enumerate(self.cfg.threads):
            regs = [None] * NREG; regs[N] = 0; regs[INTRY] = False; regs[HIT] = False
            kind = t[0]
            if kind == 'open': pc = 'O2'
            elif kind == 'close':
                pc = 'B_HIT'; regs[INTRY] = True; regs[OUT] = 'ran'
                ops[k] = (True, k, None, True); A = A | {(k, k)}; S = True
            elif kind == 'exit': pc = 'X1'
            elif kind == 'rec': pc = 'RA'
            ths.append((pc, (), tuple(regs), 'run'))
        sh = (S, A, frozenset(), None, cores, tuple(ops))
        return tuple(ths), sh

    # ---- one step of thread k; returns list of (ths, sh, events) or [] if blocked ----
    def step(self, ths, sh, k):
        pc, stack, r, status = ths[k]
        rev, mut = self.rev, self.mut
        S, A, CLR, G, cores, ops = sh
        ev = []
        def upd(pc2=None, stack2=None, r2=None, status2=None, sh2=None):
            th = (pc2 if pc2 is not None else pc, stack2 if stack2 is not None else stack,
                  r2 if r2 is not None else r, status2 if status2 is not None else status)
            return [(ths[:k] + (th,) + ths[k + 1:], sh2 if sh2 is not None else sh, ev)]
        def call(sub, ret, r2=None, sh2=None):
            return upd(pc2=sub, stack2=stack + (ret,), r2=r2, sh2=sh2)
        def ret_(r2=None, sh2=None):
            return upd(pc2=stack[-1], stack2=stack[:-1], r2=r2, sh2=sh2)
        o = k
        # ================= opener =================
        if pc == 'O2':                                   # step 2: TRACE_INACTIVE if 'exiting' (or not active)
            c = self.op_core[k]
            if cores[c][0] is not None or cores[c][1]:
                return upd(pc2='DONE', r2=setr(r, OUT, 'inactive@open'), status2='done')
            return upd(pc2='O6')
        if pc == 'O6':                                   # step 6: append (o.frame = the _run frame)
            return upd(pc2='OT', sh2=sh_set(sh, 5, ops[:o] + ((True, o, None, False),) + ops[o + 1:]))
        if pc == 'OT':                                   # enter _run's try
            return upd(pc2='C0', r2=setr(r, INTRY, True))
        if pc == 'C0':
            if rev == 4: return upd(pc2='C_ST')
            return upd(pc2='C_ON1R')
        # ---- revision 4 _commit ----
        if pc == 'C_ST':                                 # _ANCHORS[o.frame] = o
            key = ops[o][1]; c = self.op_core[k]
            late = ops[o][2] is not None or cores[c][0] is not None     # claimed, or exit began, before the store
            return upd(pc2='C_CK', r2=setr(r, LATE, late), sh2=sh_set(sh, 1, A | {(key, o)}))
        if pc == 'C_CK':                                 # step 8: claimed by a detacher, or exit began
            c = self.op_core[k]
            if 'no_recheck' in mut: return upd(pc2='C_PRE')
            claimed = ops[o][2] is not None and 'no_fin_test' not in mut
            exiting = cores[c][0] is not None and 'no_exiting_test' not in mut
            if claimed or exiting:
                r2 = setr(setr(setr(r, DOID, o), DTAG, 'open'), OUT, 'inactive@commit')
                return call('D_CLAIM', 'C_RAISE', r2=r2)
            return upd(pc2='C_PRE')
        if pc == 'C_RAISE':                              # raise TRACE_INACTIVE: to the finally
            return upd(pc2='F_D', stack2=(), r2=setr(r, INTRY, False))
        if pc == 'C_PRE':
            if 'on_before_wait' in mut: return upd(pc2='C_ORb')
            return upd(pc2='C_SN')
        if pc == 'C_ORb': return upd(pc2='C_OSb', r2=setr(r, ONL, S))
        if pc == 'C_OSb': return upd(pc2='C_SN', sh2=sh if r[ONL] else sh_set(sh, 0, True))
        if pc == 'C_SN':                                 # snapshot of announced clearers of other threads
            if 'no_wait' in mut: return upd(pc2='C_OR')
            return upd(pc2='C_WT', r2=setr(r, W, frozenset(t for t in CLR if t[0] != k)))
        if pc == 'C_WT':                                 # wait until each has withdrawn or died (blocking)
            for t in r[W]:
                if t in CLR and ('no_liveness' in mut or self.tok_alive(ths, t)): return []
            return upd(pc2='C_OR')
        if pc == 'C_OR':
            if 'on_before_wait' in mut: return upd(pc2='C_AR')
            return upd(pc2='C_OS', r2=setr(r, ONL, S))
        if pc == 'C_OS':
            return upd(pc2='C_AR', sh2=sh if r[ONL] else sh_set(sh, 0, True))
        if pc == 'C_AR':                                 # o.armed = True, last
            return upd(pc2='B_HIT', sh2=op_set(sh, o, 3, True))
        # ---- revision 3 _commit (steps 7 and 8 as specified) ----
        if pc == 'C_ON1R': return upd(pc2='C_ON1S', r2=setr(r, ONL, S))
        if pc == 'C_ON1S': return upd(pc2='C_ST3', sh2=sh if r[ONL] else sh_set(sh, 0, True))
        if pc == 'C_ST3':                                # _ANCHORS[o.frame] = o: the key is read now (None after a detach)
            key = ops[o][1]; c = self.op_core[k]
            late = ops[o][2] is not None or cores[c][0] is not None
            return upd(pc2='C_ON2R', r2=setr(r, LATE, late), sh2=sh_set(sh, 1, A | {(key, o)}))
        if pc == 'C_ON2R': return upd(pc2='C_ON2S', r2=setr(r, ONL, S))
        if pc == 'C_ON2S': return upd(pc2='C_CK3', sh2=sh if r[ONL] else sh_set(sh, 0, True))
        if pc == 'C_CK3':                                # step 8: 'exiting' only
            c = self.op_core[k]
            if cores[c][0] is not None:
                r2 = setr(setr(setr(r, DOID, o), DTAG, 'open'), OUT, 'inactive@commit')
                return call('D_CLAIM', 'C_RAISE', r2=r2)
            return upd(pc2='C_AR')
        # ---- body ----
        if pc == 'B_HIT':
            c = self.op_core[k]
            if not S and cores[c][2]: ev.append('U1')
            if r[LATE]: ev.append('P8')
            return upd(pc2='B_END', r2=setr(setr(r, OUT, 'ran'), HIT, True))
        if pc == 'B_END':
            return upd(pc2='F_D', r2=setr(r, INTRY, False))
        # ---- finally ----
        if pc == 'F_D':
            return call('D_CLAIM', 'F_N', r2=setr(setr(r, DOID, o), DTAG, 'closed'))
        if pc == 'F_N':                                  # revision 4: the owner releases o.frame
            if rev == 4: return upd(pc2='DONE', status2='done', sh2=op_set(sh, o, 1, None))
            return upd(pc2='DONE', status2='done')
        # ================= _detach(DOID) =================
        if pc == 'D_CLAIM':
            d = r[DOID]
            sh2 = sh if ops[d][2] is not None else op_set(sh, d, 2, r[DTAG])
            return upd(pc2='D_FR', sh2=sh2)
        if pc == 'D_FR':
            d = r[DOID]; fr = ops[d][1]
            if fr is None: return upd(pc2='D_NUL', r2=setr(r, DFR, None))
            return upd(pc2='D_ARM', r2=setr(r, DFR, fr))
        if pc == 'D_ARM':
            d = r[DOID]
            nxt = 'D_S' if (rev == 4 and 'anchor_first' not in mut) else 'D_A'
            return upd(pc2=nxt, r2=setr(r, DARM, ops[d][3]))
        if pc == 'D_S':                                  # revision 4: the event first ...
            return upd(pc2='D_A4', r2=setr(r, DS, S))
        if pc == 'D_A4':                                 # ... the anchor last
            d = r[DOID]; reg = (r[DFR], d) in A
            sh2 = sh
            if r[DARM] and not r[DS] and reg: sh2 = core_set(sh, self.op_core[d], 4, True)
            return upd(pc2='D_POP', sh2=sh2)
        if pc == 'D_A':                                  # revision 3: the anchor first ...
            d = r[DOID]
            return upd(pc2='D_S3', r2=setr(r, DS, (r[DFR], d) in A))
        if pc == 'D_S3':                                 # ... then the event
            d = r[DOID]; sh2 = sh
            if r[DARM] and r[DS] and not S: sh2 = core_set(sh, self.op_core[d], 4, True)
            return upd(pc2='D_POP', sh2=sh2)
        if pc == 'D_POP':
            fr = r[DFR]
            return upd(pc2='D_NUL', sh2=sh_set(sh, 1, frozenset(x for x in A if x[0] != fr)))
        if pc == 'D_NUL':                                # revision 3 nulls o.frame in every _detach
            if rev == 3 or 'detach_nulls' in mut:
                return upd(pc2='D_OFF', sh2=op_set(sh, r[DOID], 1, None))
            return upd(pc2='D_OFF')
        if pc == 'D_OFF':
            return call('U_R', 'D_RET')
        if pc == 'D_RET':
            return ret_()
        # ================= _unwind_off =================
        if pc == 'U_R':                                  # _ours() and get_events: return if clear
            if not S: return ret_()
            return upd(pc2='U_AN' if rev == 4 else ('U_T' if self.split else 'U_TC'))
        if pc == 'U_AN':                                 # announce
            tok = (k, r[N]); r2 = setr(setr(r, N, r[N] + 1), TOK, tok)
            if 'no_announce' in mut: return upd(pc2='U_T', r2=r2)
            nxt = 'U_WE' if 'withdraw_early' in mut else 'U_T'
            return upd(pc2=nxt, r2=r2, sh2=sh_set(sh, 2, CLR | {tok}))
        if pc == 'U_WE':
            return upd(pc2='U_T', sh2=sh_set(sh, 2, CLR - {r[TOK]}))
        if pc == 'U_T':                                  # test
            if A: return upd(pc2='U_WD' if rev == 4 else 'U_END')
            return upd(pc2='U_C')
        if pc == 'U_C':                                  # clear
            return upd(pc2='U_WD' if rev == 4 else 'U_RE', sh2=sh_set(sh, 0, False))
        if pc == 'U_WD':                                 # withdraw
            return ret_(r2=setr(r, TOK, None), sh2=sh_set(sh, 2, CLR - {r[TOK]}))
        if pc == 'U_TC':                                 # revision 3: test and clear, one step
            if A: return ret_()
            return upd(pc2='U_RE', sh2=sh_set(sh, 0, False))
        if pc == 'U_RE':                                 # revision 3's re-check
            return ret_(sh2=sh_set(sh, 0, True) if A else sh)
        if pc == 'U_END':
            return ret_()
        # ================= exit =================
        if pc == 'X1':
            c = self.core_of_thread[k]
            if cores[c][0] is not None or cores[c][1]:
                return upd(pc2='DONE', status2='done')   # a second exit is a no-op
            return upd(pc2='X2', sh2=core_set(sh, c, 0, k))
        if pc == 'X2':
            return upd(pc2='X3S', sh2=core_set(sh, self.core_of_thread[k], 2, False))
        if pc == 'X3S':
            return upd(pc2='X3L', r2=setr(setr(r, XL, self.appended(sh, self.core_of_thread[k])), XI, 0))
        if pc == 'X3L':
            if r[XI] < len(r[XL]):
                d = r[XL][r[XI]]
                return call('D_CLAIM', 'X3L', r2=setr(setr(setr(r, XI, r[XI] + 1), DOID, d), DTAG, 'open'))
            return upd(pc2='X5A')
        if pc in ('X5A', 'RA'):                          # the robust mutex: free, or steal from the dead
            if G is not None and self.g_alive(ths, G): return []
            g = (k, r[N]); r2 = setr(setr(r, N, r[N] + 1), TXN, g)
            return call('R_P', 'X5Z' if pc == 'X5A' else 'RZ', r2=r2, sh2=sh_set(sh, 3, g))
        if pc in ('X5Z', 'RZ'):
            sh2 = sh_set(sh, 3, None) if G == r[TXN] else sh
            if pc == 'RZ': return upd(pc2='DONE', status2='done', r2=setr(r, TXN, None), sh2=sh2)
            return upd(pc2='X8', r2=setr(r, TXN, None), sh2=sh2)
        if pc == 'X8':
            return upd(pc2='DONE', status2='done', sh2=core_set(sh, self.core_of_thread[k], 1, True))
        # ================= reconciliation =================
        if pc == 'R_P':                                  # prune: dead, not exited cores: credit stop, snapshot
            sh2 = sh; lst = ()
            for c in range(self.cfg.ncores):
                if self.core_dead(ths, sh, c) and not cores[c][1]:
                    sh2 = core_set(sh2, c, 2, False); lst += self.appended(sh, c)
            return upd(pc2='R_PL', r2=setr(setr(r, PL, lst), PI, 0), sh2=sh2)
        if pc == 'R_PL':
            if r[PI] < len(r[PL]):
                d = r[PL][r[PI]]
                return call('D_CLAIM', 'R_PL', r2=setr(setr(setr(r, PI, r[PI] + 1), DOID, d), DTAG, 'pruned'))
            if rev == 4 and 'no_anchor_sweep' not in mut: return upd(pc2='R_SS')
            return upd(pc2='R_TK')
        if pc == 'R_SS':                                 # revision 4: anchors of dead cores
            lst = tuple(sorted(x for x in A if self.core_dead(ths, sh, self.op_core[x[1]])))
            return upd(pc2='R_SL', r2=setr(setr(r, SL, lst), SI, 0))
        if pc == 'R_SL':                                 # the sweep stops the dead core's credit first (as _prune)
            if r[SI] < len(r[SL]):
                d = r[SL][r[SI]][1]
                if 'sweep_no_credit_stop' in mut:
                    return call('D_CLAIM', 'R_SP', r2=setr(setr(r, DOID, d), DTAG, 'pruned'))
                return upd(pc2='R_SC', r2=setr(setr(r, DOID, d), DTAG, 'pruned'))
            return upd(pc2='R_TK')
        if pc == 'R_SC':
            return call('D_CLAIM', 'R_SP', sh2=core_set(sh, self.op_core[r[DOID]], 2, False))
        if pc == 'R_SP':
            x = r[SL][r[SI]]
            return upd(pc2='R_SL', r2=setr(r, SI, r[SI] + 1), sh2=sh_set(sh, 1, A - {x}))
        if pc == 'R_TK':                                 # revision 4: dead announcements
            if rev == 4 and 'no_token_sweep' not in mut:
                return upd(pc2='R_OFF', sh2=sh_set(sh, 2, frozenset(t for t in CLR if self.tok_alive(ths, t))))
            return upd(pc2='R_OFF')
        if pc == 'R_OFF':
            return call('U_R', 'R_RET')
        if pc == 'R_RET':
            return ret_()
        raise AssertionError(pc)

    def fault(self, ths, sh, k):
        pc, stack, r, status = ths[k]
        kind = self.kinds[k]
        r2 = setr(setr(r, TOK, None), TXN, None)         # the frames holding a token or the mutex die
        if kind in ('open', 'close') and r[INTRY]:
            th = ('F_D', (), setr(r2, INTRY, False), 'run')
        else:
            th = ('DEAD', (), r2, 'dead')
        return ths[:k] + (th,) + ths[k + 1:]

    def invariant(self, ths, sh):
        S, A, CLR, G, cores, ops = sh
        if S: return None
        for (key, o) in A:
            if ops[o][3] and cores[self.op_core[o]][2]: return 'A0'
        return None

    def repair(self, ths, sh):
        """Fault-free continuation: each core whose exit never began is exited, then one more reconciliation."""
        cfg = self.cfg
        extra = []
        for c in range(cfg.ncores):
            if sh[4][c][0] is None and not sh[4][c][1]: extra.append(('exit', c))
        extra.append(('rec', None))
        for kind, c in extra:
            k = len(ths)
            self.kinds.append(kind); self.core_of_thread.append(c)
            regs = [None] * NREG; regs[N] = 0; regs[INTRY] = False; regs[HIT] = False
            ths = ths + (('X1' if kind == 'exit' else 'RA', (), tuple(regs), 'run'),)
            n = 0
            while ths[k][3] == 'run':
                succ = self.step(ths, sh, k)
                if not succ: raise AssertionError('repair blocked at %s' % ths[k][0])
                ths, sh, _ = succ[0]; n += 1
                if n > 10000: raise AssertionError('repair loop')
            self.kinds.pop(); self.core_of_thread.pop()
            ths = ths[:k]
        return sh

def explore(cfg, rev, split, budget, mut=frozenset()):
    m = Model(cfg, rev, split, mut)
    ths0, sh0 = m.initial()
    start = (ths0, sh0, budget)
    seen = set(); stack = [start]
    res = dict(states=0, U1_ff=0, U1_f=0, A0_ff=0, A0_f=0, HANG=0, ends_ff=0, ends_f=0,
               END_A=0, END_S=0, END_CLR=0, END_G=0, END_FIN=0, FLAG_ff=0, FLAG_f=0,
               REP_A=0, REP_S=0, REP_CLR=0, P8_ff=0, P8_f=0, outcomes={})
    nthreads = len(cfg.threads)
    while stack:
        st = stack.pop()
        h = hash(st)                                     # 64-bit state hashes, to fit the triples in memory
        if h in seen: continue
        seen.add(h); res['states'] += 1
        ths, sh, left = st
        ff = left == budget
        inv = m.invariant(ths, sh)
        if inv: res['A0_ff' if ff else 'A0_f'] += 1
        live = [k for k in range(nthreads) if ths[k][3] == 'run']
        if not live:
            S, A, CLR, G, cores, ops = sh
            flag = any(c[4] for c in cores)
            if ff:
                res['ends_ff'] += 1
                if A: res['END_A'] += 1
                if S: res['END_S'] += 1
                if CLR: res['END_CLR'] += 1
                if G is not None: res['END_G'] += 1
                if any(op[0] and op[2] is None for op in ops): res['END_FIN'] += 1
                if flag: res['FLAG_ff'] += 1
                outs = tuple(ths[k][2][OUT] for k in range(nthreads) if m.kinds[k] in ('open', 'close'))
                res['outcomes'][outs] = res['outcomes'].get(outs, 0) + 1
            else:
                res['ends_f'] += 1
                if flag: res['FLAG_f'] += 1
                sh2 = m.repair(ths, sh)
                if sh2[1]: res['REP_A'] += 1
                if sh2[0]: res['REP_S'] += 1
                if sh2[2]: res['REP_CLR'] += 1
                if any(c[4] for c in sh2[4]): res['FLAG_f'] += 0
            continue
        moved = False
        for k in live:
            for (ths2, sh2, ev) in m.step(ths, sh, k):
                moved = True
                if 'U1' in ev: res['U1_ff' if ff else 'U1_f'] += 1
                if 'P8' in ev: res['P8_ff' if ff else 'P8_f'] += 1
                stack.append((ths2, sh2, left))
            if left > 0:
                stack.append((m.fault(ths, sh, k), sh, left - 1))
        if not moved:
            res['HANG'] += 1
    return res

# ---------------- the configurations: every pair of concurrent transitions ----------------
X, Y = 0, 1
CONFIGS = [
    Cfg('open(X) || exit(X)', [('open', X), ('exit', X)], 1, ['open/exit same tracer', 'close/exit same tracer (after the body)']),
    Cfg('close(X) || exit(X)', [('close', X), ('exit', X)], 1, ['close/exit same tracer']),
    Cfg('open(X) || open(X)', [('open', X), ('open', X)], 1, ['open/open, open/close, close/close: same tracer']),
    Cfg('open(X) || open(Y)', [('open', X), ('open', Y)], 2, ['open/open, open/close, close/close: two tracers']),
    Cfg('open(Y) || exit(X)', [('open', Y), ('exit', X)], 2, ['open/exit, close/exit: other tracer (retire, reconcile)']),
    Cfg('exit(X) || exit(X)', [('exit', X), ('exit', X)], 1, ['exit/exit same tracer']),
    Cfg('exit(X) || exit(Y)', [('exit', X), ('exit', Y)], 2, ['exit/exit two tracers']),
    Cfg('rec || open(X), X facade dead', [('rec', None), ('open', X)], 1, ['reconcile(prune)/open, reconcile(prune)/close'], facade_dead=(X,)),
    Cfg('rec || open(Y)', [('rec', None), ('open', Y)], 2, ['reconcile/open, reconcile/close (nothing to prune)']),
    Cfg('rec || exit(X)', [('rec', None), ('exit', X)], 1, ['reconcile/exit']),
    Cfg('rec || rec', [('rec', None), ('rec', None)], 1, ['reconcile/reconcile']),
    Cfg('open(X) || open(X) || exit(X)', [('open', X), ('open', X), ('exit', X)], 1, ['open/exit with a second section (triple)']),
    Cfg('open(X) || exit(X) || exit(X)', [('open', X), ('exit', X), ('exit', X)], 1, ['exit/exit same tracer with a section (triple)']),
    Cfg('open(X) || exit(X) || rec', [('open', X), ('exit', X), ('rec', None)], 1, ['exit faulted after X1, then prune, vs open (triple)']),
    Cfg('open(X) || open(X) || exit(Y)', [('open', X), ('open', X), ('exit', Y)], 2, ['two sections and a retire (revision 3 m1)']),
]

def fmt(r):
    bad = []
    for key in ('P8_ff', 'P8_f', 'U1_ff', 'U1_f', 'A0_ff', 'A0_f', 'HANG', 'END_A', 'END_S', 'END_CLR', 'END_G', 'END_FIN', 'FLAG_ff', 'FLAG_f', 'REP_A', 'REP_S', 'REP_CLR'):
        if r[key]: bad.append('%s=%d' % (key, r[key]))
    return ', '.join(bad) if bad else 'ok'

if __name__ == '__main__':
    which = sys.argv[1] if len(sys.argv) > 1 else 'main'
    if which == 'main':
        for cfg in CONFIGS:
            triple = len(cfg.threads) == 3
            for rev, split in ((3, False), (3, True), (4, False)):
                name = 'rev3-split' if split else 'rev%d' % rev
                # triples: revision 3 fault-free only (its defects already show there); revision 4 with 0 or 1 fault
                for budget in (((0, 1) if rev == 4 else (0,)) if triple else (0, 1, 2)):
                    t0 = time.time()
                    r = explore(cfg, rev, split, budget)
                    outs = ' '.join('%s:%d' % ('/'.join(str(x) for x in k), v) for k, v in sorted(r['outcomes'].items(), key=str)) if budget == 0 else ''
                    print('%-34s %-10s faults<=%d %8d states %5d/%-6d ends  %s%s  (%.0fs)' % (
                        cfg.name, name, budget, r['states'], r['ends_ff'], r['ends_f'], fmt(r),
                        ('  | outcomes ' + outs) if outs else '', time.time() - t0))
                    sys.stdout.flush()
    elif which == 'mutants':
        MUTS = ['no_announce', 'withdraw_early', 'no_wait', 'on_before_wait', 'detach_nulls', 'no_recheck',
                'no_fin_test', 'no_exiting_test', 'anchor_first', 'no_anchor_sweep', 'no_token_sweep', 'no_liveness', 'sweep_no_credit_stop']
        if len(sys.argv) > 2: MUTS = sys.argv[2:]
        for mu in MUTS:
            found = []
            for cfg in CONFIGS:
                # pairs, and the smaller triples (the largest, open||open||exit(X), is skipped for time)
                if cfg.name == 'open(X) || open(X) || exit(X)': continue
                for budget in ((0, 1) if len(cfg.threads) == 3 else (0, 1, 2)):
                    r = explore(cfg, 4, False, budget, frozenset([mu]))
                    f = fmt(r)
                    if f != 'ok':
                        found.append('%s faults<=%d: %s' % (cfg.name, budget, f)); break
                if found and len(found) >= 3: break
            print('%-16s %s' % (mu, (' | '.join(found)) if found else 'NOT DETECTED by any configuration'))
            sys.stdout.flush()
