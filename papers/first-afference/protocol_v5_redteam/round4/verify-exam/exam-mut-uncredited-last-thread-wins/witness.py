"""Witness: two threads, alive at the same time (barrier, so their idents differ), each open
section S and inside it run a private event loop that dispatches g once via call_soon (so g's
walk hits Handle._run: a `dispatched` uncredited call). Gate G declares g in its own section,
which only runs f-free work, so G refuses NOT_EXERCISED and prints the dispatched count.
Original: record() sums per-thread buckets -> dispatched {g: 2}, message 'dispatched {...: 2}'.
Mutant (`disp[k] = v`): the last thread's value wins -> {g: 1}."""
import sys, json
sys.path.insert(0, "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt4/verify-exam")
from b7lib import both
MUT = "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt4/verify-exam/exam-mut-uncredited-last-thread-wins"
BODY = r'''
import asyncio, re
mod = mkmod("b7ul_fx", "def f():\n    return 1\ndef g():\n    return 2\n")
exp = mkexp({"G": {"exercises": ["b7ul_fx:g"]}, "S": {"exercises": ["b7ul_fx:f"]}})
bar = threading.Barrier(2)
idents = []
with coverage_trace(exp) as cov:
    def shard():
        idents.append(threading.get_ident())
        def body():
            mod.f()
            loop = asyncio.new_event_loop()
            try:
                loop.call_soon(mod.g)          # dispatched: runs under Handle._run
                loop.call_soon(loop.stop)
                loop.run_forever()
            finally:
                loop.close()
            bar.wait(timeout=10)               # both threads alive together: distinct idents
        cov.run("S", body)
    ts = [threading.Thread(target=shard) for _ in range(2)]
    for t in ts: t.start()
    for t in ts: t.join(timeout=20)
    cov.run("G", lambda: None)                 # G's section opened, g never on its stack
rec = cov.record()
s = score(exp, rec)
m = re.search(r"dispatched (\{[^}]*\})", s.get("refused", ""))
out(distinct_threads=len(set(idents)), dispatched=rec["uncredited"]["dispatched"],
    unattributed=rec["uncredited"]["unattributed"], code=s.get("refused", "PASS")[:24],
    message_dispatched=m.group(1) if m else None)
'''
o, m = both(MUT, BODY)
sep = (o["dispatched"] == {"b7ul_fx:g": 2} and m["dispatched"] == {"b7ul_fx:g": 1}
       and o["message_dispatched"] != m["message_dispatched"])
print("SEPARATES" if sep else "NO SEPARATION")
