from rtlib import *
import fx_cm, threading, importlib
e = exp(spec(G={"exercises": ["fx_cm:K.make", "fx_cm:K.__call__", "fx_cm:boom", "fx_cm:rec"]}))
with coverage_trace(e) as cov:
    with cov.section("G"):
        fx_cm.K.make()(); getattr(fx_cm, "rec")(3)
        try: fx_cm.boom()
        except ValueError: pass
print("classmethod/__call__/raising/recursion/getattr:", score(e, cov.record()))
e = exp(spec(G={"exercises": ["fx_cm:rec"]}))
with coverage_trace(e) as cov:
    importlib.reload(fx_cm)
    with cov.section("G"): fx_cm.rec(0)
print("reload after entry:", score(e, cov.record()))
