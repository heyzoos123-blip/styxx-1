"""round1_module/t08_crashes.py, rewritten: (1) targets whose resolution raises something other than
ImportError/AttributeError (a module raising at import, a syntax error, a self-referential __wrapped__);
(2) a target with a trailing newline (the repro tested the private _TARGET_RE; here through the public
Experiment); (3) malformed traces fed to score() and check_metrics(); (4) check_metrics on a list."""
import copy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r1m_fx import BROKEN, CYCLE, SYNTAX


def main(api):
    out = {}
    api.fixture("rp_fx_simple", 'def f(): return 1\n')
    for name, src in (("rp_fx_broken", BROKEN), ("rp_fx_syntax", SYNTAX), ("rp_fx_cycle", CYCLE)):
        path = os.path.join(api.fxdir, name + ".py")
        open(path, "w").write(src)
        sys.modules.pop(name, None)
        e = api.exp({"G": [f"{name}:f"]})
        out[f"resolve_{name}"] = api.trace(e)
    out["target_trailing_newline"] = api.attempt(lambda: api.exp({"G": ["rp_fx_simple:f\n"]}).score({"m": 1.0}).verdict)
    e = api.exp({"G": ["rp_fx_simple:f"]})
    import rp_fx_simple as fx
    cov = api.coverage_trace(e)
    with cov:
        cov.run("G", fx.f)
    good = cov.record()

    def mk(mut):
        r = copy.deepcopy(good)
        try:
            mut(r)
        except BaseException as ex:                    # noqa: BLE001
            return {"mutation_failed": type(ex).__name__}
        return r
    cases = {"sections_int_key": mk(lambda r: r["sections"].__setitem__(1, "x")),
             "sections_none_key": mk(lambda r: r["sections"].__setitem__(None, "x")),
             "section_entry_tuple_key": mk(lambda r: r["sections"]["G"][0].__setitem__(("a",), 1)),
             "uncredited_not_dict": mk(lambda r: r.__setitem__("uncredited", [1])),
             "problems_str": mk(lambda r: r.__setitem__("problems", "x"))}
    for k, tr in cases.items():
        out[f"score_{k}"] = api.score(e, tr)
        out[f"check_metrics_{k}"] = api.metrics(e, {"m": 1.0, "coverage_trace": tr})
    out["check_metrics_list"] = api.metrics(e, [1])
    return out
