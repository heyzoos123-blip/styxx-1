"""round2_exam/repro.py, rewritten (the round-2 exam author's repros; round2_exam/ falls in the text's range
"round1_module/ through round4/", see SPEC_GAPS.md, Revision 13 follow-ups): R06 a target called only after its
section closed (a task created in run_async G, awaited after); R02b two gates whose targets are one function under
two names (an alias); malformed traces (R13b a non-string key in sections, R13c a non-string key inside an opening
and a section value that is not a list of openings, check_metrics on it; R13d check_metrics with a non-string key);
TARGET_SET (v5e's 'targets' map; in v5f, the declared target missing from an opening's calls is the honest shape,
an empty calls); BAD_COUNT (an undeclared name in an opening's calls); R14b a non-ASCII target; R10b a tracer
re-entered after its exit; R05b a thread started from a thread started in the section."""
import asyncio, copy, threading

FX = "def target(): return 1\nalias = target\ndef other(): return 2\n"


def main(api):
    fx = api.fixture("rp_rtfx", FX)
    T, A = "rp_rtfx:target", "rp_rtfx:alias"
    out = {}

    async def work():
        await asyncio.sleep(0)
        fx.target()
    box = {}

    async def g_body():
        box["t"] = asyncio.ensure_future(work())

    async def drive(c):
        await c.run_async("G", g_body)
        await box["t"]
    out["R06_after_close"] = api.trace(api.exp({"G": [T]}), lambda c: asyncio.run(drive(c)))
    out["R02b_alias"] = api.trace(api.exp({"G": [T], "H": [A]}), lambda c: c.run("G", fx.target), lambda c: c.run("H", fx.target))
    e = api.exp({"G": [T]})
    cov = api.coverage_trace(e)
    with cov:
        cov.run("G", fx.target)
    base = cov.record()

    def edited(fn):
        r = copy.deepcopy(base)
        fn(r)
        return r
    cases = {"R13b_sections_int_key": edited(lambda r: r["sections"].__setitem__(7, [])),
             "R13c_opening_int_key": edited(lambda r: r["sections"]["G"][0].__setitem__(7, 1)),
             "R13c_section_list_of_str": edited(lambda r: r["sections"].__setitem__("G", [T])),
             "R13d_calls_none_key": edited(lambda r: r["sections"]["G"][0]["calls"].__setitem__(None, 1)),
             "TARGET_SET_empty_calls": edited(lambda r: r["sections"]["G"][0].__setitem__("calls", {})),
             "BAD_COUNT_undeclared_name": edited(lambda r: r["sections"]["G"][0]["calls"].__setitem__("rp_rtfx:zzz", 1))}
    for k, r in cases.items():
        out[k] = {"score": api.score(e, r), "metrics": api.metrics(e, {"m": 1.0, "coverage_trace": r})}
    out["R14b_non_ascii_target"] = api.attempt(lambda: api.exp({"G": ["rp_rtfx:targét"]}) and "accepted")
    cov = api.coverage_trace(e)
    with cov:
        pass
    r = {"reenter": api.attempt(lambda: cov.__enter__() is cov)}
    if r["reenter"].get("returned") is True:
        r["run"] = api.attempt(cov.run, "G", fx.target)
        r["exit"] = api.attempt(lambda: bool(cov.__exit__(None, None, None)))
    r["record"] = api.record(cov)
    out["R10b_reenter_exited"] = r

    def gc_body():
        def outer():
            th = threading.Thread(target=fx.target)
            th.start()
            th.join()
        th = threading.Thread(target=outer)
        th.start()
        th.join()
    out["R05b_grandchild"] = api.trace(e, lambda c: c.run("G", gc_body))
    return out
