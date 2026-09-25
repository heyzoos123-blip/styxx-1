# CPython #130279 and revision 4's _await_clearers: its wait loop is in its own frame, with no try, called from
# _commit, which _run calls inside its try body. An exception raised at a back-edge escapes the try table of the
# frame that holds the back-edge; does it also skip the caller's finally? Method of rev1/p10: a sys.monitoring
# INSTRUCTION tool raises KeyboardInterrupt at the back-edge offset (JUMP_BACKWARD, or JUMP_BACKWARD_NO_INTERRUPT).
#   control: the loop is inside the try body itself (the #130279 shape): the finally is skipped on 3.13 (p10);
#   rev 4:   the loop is in a callee with no try (await_clearers -> commit -> run's try): the finally must run.
import sys, dis
M = sys.monitoring; E = M.events
ran = []
def control(n):
    try:
        i = 0
        while i < n: i += 1
    finally:
        ran.append('control finally')
def await_clearers(n):                    # the shape of _await_clearers: a loop, no try
    i = 0
    while i < n: i += 1
def commit(n): await_clearers(n)          # the shape of _commit: no loop, no try
def run(n):                               # the shape of _run: the single try/finally
    try:
        commit(n)
    finally:
        ran.append('run finally')
def backedges(code):
    return [i.offset for i in dis.get_instructions(code) if i.opname.startswith('JUMP_BACKWARD')]
def trial(target_code, fn):
    offs = set(backedges(target_code)); fired = [0]
    def cb(code, off):
        if code is target_code and off in offs and not fired[0]: fired[0] = 1; raise KeyboardInterrupt
    M.use_tool_id(5, 'inj'); M.register_callback(5, E.INSTRUCTION, cb); M.set_local_events(5, target_code, E.INSTRUCTION)
    ran.clear()
    try: fn(3)
    except KeyboardInterrupt: pass
    M.set_local_events(5, target_code, 0); M.register_callback(5, E.INSTRUCTION, None); M.free_tool_id(5)
    return fired[0], list(ran)
v = sys.version.split()[0]
f1, r1 = trial(control.__code__, control)
f2, r2 = trial(await_clearers.__code__, run)
print(v, 'control (loop in the try body): back-edge fired %d, finally ran: %s' % (f1, bool(r1)))
print(v, 'rev 4 shape (loop in a callee with no try): back-edge fired %d, run finally ran: %s' % (f2, bool(r2)))
