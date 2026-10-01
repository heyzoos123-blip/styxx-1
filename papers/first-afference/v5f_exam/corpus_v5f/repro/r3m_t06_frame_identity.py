"""round3_module/t06_frame_identity.py, rewritten: F1 a method using super() (__class__ cell); F2 a generator with
a free variable resumed 3 times; F3 a coroutine with a free variable (asyncio.run inside the section); F4 a cell
argument plus a free variable; F5 a lazy-init nonlocal, first call in the section; F6 a recursive closure."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r3m_fx import FRAMES


def main(api):
    m = api.fixture("rp_fx3_frames", FRAMES)
    T = lambda t, fn: api.trace(api.exp({"G": [f"rp_fx3_frames:{t}"]}), lambda c: c.run("G", fn))
    return {"F1_super": T("Model.fit", lambda: m.Model().fit(1)), "F2_generator": T("gen", lambda: len(list(m.gen(2)))),
            "F3_coroutine": T("coro", lambda: asyncio.run(m.coro(1))),
            "F4_cellarg": T("cellarg", lambda: len([m.cellarg(1), m.cellarg(2)])),
            "F5_lazy_nonlocal": T("get", lambda: len([m.get(), m.get()])), "F6_recursive_closure": T("walk", lambda: m.walk(5))}
