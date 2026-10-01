"""round4/attribution/r1/a07_call_tracing_credit.py, rewritten: a settrace callback (a debugger) that runs the
declared target with sys.call_tracing at the section body's first line event; the section's own code never calls
it."""
import sys


def main(api):
    fx = api.fixture("rp_a07_fix", "def f(): return 1\n")
    e = api.exp({"G": ["rp_a07_fix:f"]})
    done = []

    def body():
        x = 1
        x += 1
        return x

    def tracer(frame, event, arg):
        if frame.f_code is body.__code__ and event == "line" and not done:
            done.append(1)
            sys.call_tracing(fx.f, ())
        return tracer

    def run(c):
        sys.settrace(tracer)
        try:
            return c.run("G", body)
        finally:
            sys.settrace(None)
    return {"call_tracing": api.trace(e, run), "callback_ran": bool(done)}
