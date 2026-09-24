import sys, asyncio
from rtlib import *
import fx3_frames as m
def run(target, body, label):
    e = exp(spec(G={"exercises": [target]}))
    with coverage_trace(e) as cov:
        with cov.section("G"):
            out = body()
    r = cov.record()
    print(f"  {label}: result={out!r} sections={r['sections']} impostors={r['impostors']}")
    return score(e, r)
print(sys.version.split()[0])
attempt("F1 method using super() (__class__ cell)", lambda: run("fx3_frames:Model.fit", lambda: m.Model().fit(1), "F1"))
attempt("F2 generator with free var, 3 resumes", lambda: run("fx3_frames:gen", lambda: list(m.gen(2)), "F2"))
attempt("F3 coroutine with free var", lambda: run("fx3_frames:coro", lambda: asyncio.run(m.coro(1)), "F3"))
attempt("F4 cell argument + free var (f_locals side effects?)", lambda: run("fx3_frames:cellarg", lambda: [m.cellarg(1), m.cellarg(2)], "F4"))
attempt("F5 lazy-init nonlocal, first call in section", lambda: run("fx3_frames:get", lambda: [m.get(), m.get()], "F5"))
attempt("F6 recursive closure", lambda: run("fx3_frames:walk", lambda: m.walk(5), "F6"))
