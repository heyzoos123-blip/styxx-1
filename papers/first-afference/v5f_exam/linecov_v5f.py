"""linecov_v5f.py: G_COVER's frozen LINE-event tool (revision 3, MF6), written by the exam author.

sys.monitoring tool id 0 (no exam tool or case uses it), with global LINE events. The callback records
(co_filename, line) for code whose co_filename is the implementation's path and returns None there; for
all other code it returns DISABLE, so it never disables a location in machinery code.

The region's executable lines (G_COVER, "Executable lines"): for each region code object, meaning the
_v5_faultpoints() code objects read before any tracer exists plus the scoring functions of the SM2 region,
{line for _, _, line in code.co_lines() if line is not None} - {code.co_firstlineno}.

Use as a library (start/stop/lines) or run a pass under it:
    python linecov_v5f.py --impl PATH --out LINES.json -- <script> [args...]
The pass's own processes each start the tool (the env var V5F_LINECOV names the file to append to).
"""
import atexit, json, os, runpy, sys

TOOL = 0
_STATE = {"path": None, "lines": set(), "on": False}

SCORING = ("Experiment._check_coverage", "Experiment.check_metrics", "Experiment.score", "_check_trace_shape", "_finite")


def _cb(code, line):
    if code.co_filename == _STATE["path"]:
        _STATE["lines"].add(line)
        return None
    return sys.monitoring.DISABLE


def start(impl_path):
    mon = sys.monitoring
    _STATE["path"] = os.path.abspath(impl_path)
    mon.use_tool_id(TOOL, "linecov_v5f")
    mon.register_callback(TOOL, mon.events.LINE, _cb)
    mon.set_events(TOOL, mon.events.LINE)
    _STATE["on"] = True


def stop():
    if _STATE["on"]:
        mon = sys.monitoring
        mon.set_events(TOOL, 0)
        mon.register_callback(TOOL, mon.events.LINE, None)
        mon.free_tool_id(TOOL)
        _STATE["on"] = False
    return set(_STATE["lines"])


def region_codes(P):
    """The region code objects: _v5_faultpoints() plus the SM2 scoring functions (by name)."""
    codes = dict(P._v5_faultpoints())
    for q in SCORING:
        obj = P
        for part in q.split("."):
            obj = getattr(obj, part)
        codes[q] = obj.__code__
    return codes


def executable_lines(P, names=None):
    out = {}
    for k, code in region_codes(P).items():
        if names is not None and k not in names:
            continue
        out[k] = sorted({ln for _, _, ln in code.co_lines() if ln is not None} - {code.co_firstlineno})
    return out


def dump_at_exit(outfile):
    def _dump():
        lines = stop()
        with open(outfile, "a") as fh:
            fh.write(json.dumps(sorted(lines)) + "\n")
    atexit.register(_dump)


def read(outfile):
    seen = set()
    if os.path.exists(outfile):
        for ln in open(outfile):
            if ln.strip():
                seen.update(json.loads(ln))
    return seen


if __name__ == "__main__":
    a = sys.argv[1:]
    impl = a[a.index("--impl") + 1]
    out = a[a.index("--out") + 1]
    rest = a[a.index("--") + 1:]
    os.environ["V5F_LINECOV"] = out + "|" + os.path.abspath(impl)
    start(impl)
    dump_at_exit(out)
    sys.argv = rest
    runpy.run_path(rest[0], run_name="__main__")
