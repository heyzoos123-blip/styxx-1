from rtlib import *
import fx_simple as fs, copy, math
e = exp(spec(G={"exercises": ["fx_simple:f"]}))
with coverage_trace(e) as cov:
    with cov.section("G"): fs.f()
good = cov.record()
print("good:", score(e, good))
def mut(fn):
    r = copy.deepcopy(good); fn(r); return r
class Weird(dict):
    def get(self, *a): raise RuntimeError("weird get")
cases = {
  "trace=None": None, "trace=list": [1, 2], "trace=str": "x", "trace=int 10**400": 10**400,
  "tracer=None": mut(lambda r: r.update(tracer=None)),
  "tracer=list": mut(lambda r: r.update(tracer=[1])),
  "tracer=dict": mut(lambda r: r.update(tracer={})),
  "tracer=nan": mut(lambda r: r.update(tracer=float('nan'))),
  "gates_sha=None": mut(lambda r: r.update(gates_sha256=None)),
  "gates_sha=bytes": mut(lambda r: r.update(gates_sha256=b"\xff")),
  "targets=list": mut(lambda r: r.update(targets=["fx_simple:f"])),
  "targets=None": mut(lambda r: r.update(targets=None)),
  "sections=None": mut(lambda r: r.update(sections=None)),
  "sections=list": mut(lambda r: r.update(sections=[["G", {}]])),
  "section G=None": mut(lambda r: r["sections"].update(G=None)),
  "section G=list": mut(lambda r: r["sections"].update(G=["fx_simple:f"])),
  "section G=str": mut(lambda r: r["sections"].update(G="fx_simple:f")),
  "count huge": mut(lambda r: r["sections"]["G"].update({"fx_simple:f": 10**4000})),
  "count nan": mut(lambda r: r["sections"]["G"].update({"fx_simple:f": float('nan')})),
  "count inf": mut(lambda r: r["sections"]["G"].update({"fx_simple:f": float('inf')})),
  "count True": mut(lambda r: r["sections"]["G"].update({"fx_simple:f": True})),
  "count 0": mut(lambda r: r["sections"]["G"].update({"fx_simple:f": 0})),
  "count -1": mut(lambda r: r["sections"]["G"].update({"fx_simple:f": -1})),
  "count '1'": mut(lambda r: r["sections"]["G"].update({"fx_simple:f": "1"})),
  "count dict": mut(lambda r: r["sections"]["G"].update({"fx_simple:f": {}})),
  "section extra key None": mut(lambda r: r["sections"].update({None: {}})),
  "section G key int": mut(lambda r: r["sections"]["G"].update({1: 1})),
  "target key unhashable?": mut(lambda r: r.update(targets={"fx_simple:f": [[]]})),
  "targets extra": mut(lambda r: r["targets"].update({"x:y": "z"})),
  "dict subclass .get raises": Weird(good),
  "missing tracer": {k: v for k, v in good.items() if k != "tracer"},
}
for name, tr in cases.items():
    for fn in ("score", "check_metrics"):
        try:
            if fn == "score": v = e.score({"m": 1.0, "coverage_trace": tr}); out = f"VERDICT {v.verdict}"
            else:
                o = e.check_metrics({"m": 1.0, "coverage_trace": tr}); out = f"ok note={str(o.get('G:exercises',{}).get('note'))[:60]}"
        except GateSpecError as ex: out = "GateSpecError " + str(ex)[:60]
        except BaseException as ex: out = f"ESCAPED {type(ex).__name__}: {str(ex)[:80]}"
        print(f"{name:28s} {fn:13s} {out}")
for res in (None, [], "s", 5, {"m": float('nan')}, {"m": 1.0, "coverage_trace": good, 1: 2}):
    for fn in ("score", "check_metrics"):
        try: getattr(e, fn)(res); out = "ok"
        except GateSpecError as ex: out = "GateSpecError"
        except BaseException as ex: out = f"ESCAPED {type(ex).__name__}: {str(ex)[:80]}"
        print(f"result={str(res)[:30]:30s} {fn:13s} {out}")
