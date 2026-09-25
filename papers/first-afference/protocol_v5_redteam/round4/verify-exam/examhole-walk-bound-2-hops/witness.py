"""Witness: provenance walks the own-dict __wrapped__ chain for up to 16 hops."""
import json, sys
sys.path.insert(0, "/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt4/verify-exam/examhole-walk-bound-2-hops")
import witlib
P = witlib.load(sys.argv[1])
witlib.fixture("ww_deco", """
    import functools
    def retry(fn):
        @functools.wraps(fn)
        def w(*a, **k): return fn(*a, **k)
        return w
    def log_calls(fn):
        @functools.wraps(fn)
        def w(*a, **k): return fn(*a, **k)
        return w
    def timed(fn):
        @functools.wraps(fn)
        def w(*a, **k): return fn(*a, **k)
        return w
    def wraps_n(fn, n):
        for _ in range(n):
            fn = retry(fn)
        return fn
""")
import textwrap
m = witlib.fixture("ww_svc", textwrap.dedent("""
    from ww_deco import retry, log_calls, timed, wraps_n
    @retry
    @log_calls
    @timed
    def fetch(x): return x
    def _inner(x): return x
    """) + "".join(f"chain{n} = wraps_n(_inner, {n})\n" for n in range(1, 18)))
out = {}
e = witlib.exp(P, {"G": {"exercises": ["ww_svc:fetch"]}})
out["W4a_three_stacked_wraps"] = witlib.outcome(P, e, lambda cov: cov.run("G", m.fetch, 1))
# boundary sweep: which chain depths are accepted at resolution
acc = []
for n in range(1, 18):
    try:
        P._resolve_target(f"ww_svc:chain{n}")
        acc.append(n)
    except P.GateSpecError as ex:
        assert str(ex).startswith("[V5:FOREIGN_DEFINITION]"), ex
out["W4b_accepted_depths"] = acc
print(json.dumps(out))
