from rtlib import *
import fx2_timed as m, types, fx2_clone as c
def a():
    # gate G declares score_all; the harness only runs the cheap path, obtained at run time
    e = exp(spec(G={"exercises": ["fx2_timed:score_all"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"):
            h = m.get_cheap_handler()      # second function sharing wrapper's code, born now
            h(1)                           # score_all is NEVER called
    return score(e, cov.record())
attempt("A1a runtime decoration after trace entry (score_all never called)", a)
def b():
    # lazily imported module that applies the same no-wraps decorator
    import sys, textwrap, pathlib
    pathlib.Path("fx2_plugin.py").write_text("import fx2_timed\n@fx2_timed.timed\ndef plugin_entry(x):\n    return -x\n")
    sys.modules.pop("fx2_plugin", None)
    e = exp(spec(G={"exercises": ["fx2_timed:score_all"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"):
            import fx2_plugin; fx2_plugin.plugin_entry(3)
    return score(e, cov.record())
attempt("A1b lazily imported plugin using same decorator", b)
def cl():
    e = exp(spec(G={"exercises": ["fx2_clone:target"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"):
            f2 = types.FunctionType(c.target.__code__, {"__builtins__": __builtins__}, "clone")
            f2(2)
    return score(e, cov.record())
attempt("A1c FunctionType clone made after entry", cl)
def reassign():
    e = exp(spec(G={"exercises": ["fx2_clone:target"]}))
    with coverage_trace(e) as cov:
        with cov.section("G"):
            def mock(x): return 0
            saved = mock.__code__
            mock.__code__ = c.target.__code__     # no; demonstrates __code__ assignment path
            mock(1)
    return score(e, cov.record())
attempt("A1d __code__ assignment after entry", reassign)
