"""gcover_v5f.py: G_COVER's four-pass measurement, written by the exam author from the design text (G_COVER).

Every executable line of the region (linecov_v5f.executable_lines: the _v5_faultpoints() code objects plus the
SM2 scoring functions) must be seen by the frozen LINE tool (linecov_v5f.py, tool id 0) in at least one pass:
  1. the frozen runner's --fast mode (every case once in its frozen placement; subprocess cases included);
  2. the frozen crash sweep at the frozen stride 3, with the background variant and the fork scenario (its
     G_FI verdict is discarded: G_FI's verdict comes from a run with no coverage tool);
  3. the frozen fuzzer with its frozen seeds;
  4. the frozen direct-call driver cover_driver_v5f.py, counted for the named list only.
"The tool is enabled at the start of every process each pass creates": passes 1-3 run with a sitecustomize
that starts linecov_v5f in every interpreter the pass starts (each writes its lines to the pass's file at
exit, and before os._exit). A forked child writes its lines too (the fork scenario's child in pass 2); in
pass 1 the lines of forked processes are dropped, since V47's pool workers are not measured. Pass 4 runs the
driver as it is (it starts the tool itself) and contributes its named functions' covered lines.

Usage: python gcover_v5f.py [--impl PATH] [--passes 1234] [--deps DIR] [--out RESULT.json]
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ARGV = list(sys.argv)
if HERE not in sys.path:
    sys.path.append(HERE)
import v5f_tmp      # noqa: E402  the pass files are removed at exit; each pass's TMPDIR when it returns
import linecov_v5f  # noqa: E402


def _opt(n, d=None):
    return ARGV[ARGV.index(n) + 1] if n in ARGV else d


IMPL = os.path.abspath(_opt("--impl", os.path.join(HERE, "ref_v5f.py")))
DEPS = _opt("--deps", os.environ.get("V5F_DEPS_PATH"))
NAMED = ("_on_entry", "_on_exit", "_on_unwind", "_outcome", "_publish", "_forget_in_child")

SITECUSTOMIZE = '''
import atexit, json, os, sys
_spec = os.environ.get("V5F_LINECOV")
if _spec:
    _out, _impl, _home = _spec.split("|")
    if _home not in sys.path:
        sys.path.append(_home)
    import linecov_v5f as _lc
    _lc.start(_impl)
    _st = {"forked": False, "dumped": False}
    os.register_at_fork(after_in_child=lambda: _st.__setitem__("forked", True))

    def _dump():
        if _st["dumped"]:
            return
        _st["dumped"] = True
        lines = sorted(_lc._STATE["lines"])
        with open(_out, "a") as fh:
            fh.write(json.dumps({"pid": os.getpid(), "forked": _st["forked"], "argv": sys.argv[:6],
                                 "lines": lines}) + "\\n")
    atexit.register(_dump)
    _real_exit = os._exit

    def _exit(code):
        try:
            _dump()
        except BaseException:
            pass
        _real_exit(code)
    os._exit = _exit
'''


def run_pass(n, work, py):
    lines = os.path.join(work, f"pass{n}.lines")
    env = dict(os.environ)
    if DEPS:
        env["V5F_DEPS_PATH"] = DEPS
    if n != 4:
        site = os.path.join(work, "site")
        env["PYTHONPATH"] = site + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        env["V5F_LINECOV"] = f"{lines}|{IMPL}|{HERE}"
    out = os.path.join(work, f"pass{n}.json")
    cmd = {1: [py, os.path.join(HERE, "run_protocol_v5f_exam.py"), "--impl", IMPL, "--fast", "--out", out],
           2: [py, os.path.join(HERE, "crash_sweep_v5f.py"), "--impl", IMPL, "--stride", "3", "--out", out],
           3: [py, os.path.join(HERE, "fuzz_v5f.py"), "--impl", IMPL, "--out", out],
           4: [py, os.path.join(HERE, "cover_driver_v5f.py"), "--impl", IMPL, "--out", out]}[n]
    t0 = time.monotonic()
    r = v5f_tmp.child_run(cmd, env=env, capture_output=True, text=True, timeout=14400)
    v5f_tmp.check_child(r.stderr if r.returncode != v5f_tmp.DISK_LOW_STATUS else "ENOSPC", f"pass {n}")
    info = {"rc": r.returncode, "seconds": round(time.monotonic() - t0, 1),
            "tail": (r.stdout.strip().splitlines() or [""])[-1][:300]}
    try:
        info["result"] = json.load(open(out))
    except (OSError, ValueError):
        info["result"] = None
        info["stderr"] = r.stderr[-600:]
    seen, procs, dropped = set(), 0, 0
    if n != 4 and os.path.exists(lines):
        for ln in open(lines):
            d = json.loads(ln)
            procs += 1
            if n == 1 and d["forked"]:
                dropped += 1
                continue
            seen.update(d["lines"])
    info["processes_measured"] = procs
    info["forked_dropped"] = dropped
    return seen, info


def main():
    import importlib.util
    py = sys.executable
    passes = [int(c) for c in _opt("--passes", "1234")]
    work = v5f_tmp.workdir("v5f_gcover_")
    os.makedirs(os.path.join(work, "site"))
    open(os.path.join(work, "site", "sitecustomize.py"), "w").write(SITECUSTOMIZE)
    spec = importlib.util.spec_from_file_location("gcover_impl", IMPL)
    P = importlib.util.module_from_spec(spec)
    sys.modules["gcover_impl"] = P
    spec.loader.exec_module(P)
    exe = linecov_v5f.executable_lines(P)
    t0 = time.monotonic()
    res = {"impl": IMPL, "python": sys.version.split()[0], "passes": {}}
    seen_by = {}
    for n in passes:
        v5f_tmp.disk_guard(what=f"pass {n}")
        seen, info = run_pass(n, work, py)
        if n == 4:
            r = info.get("result") or {}
            miss = r.get("missing", None)
            seen = set()
            if miss is not None:
                for k in NAMED:
                    seen.update(ln for ln in exe.get(k, []) if ln not in miss.get(k, []))
            info["driver_verdict"] = r.get("verdict")
        seen_by[n] = seen
        res["passes"][str(n)] = {k: v for k, v in info.items() if k != "result"}
        res["passes"][str(n)]["region_lines_seen"] = sum(1 for k, v in exe.items() for ln in v if ln in seen)
        if n in (1, 2, 3) and info.get("result"):
            r = info["result"]
            res["passes"][str(n)]["run_verdict"] = r.get("verdict", r.get("G_FI"))
        print(f"pass {n}: rc {info['rc']}, {info['seconds']} s, {res['passes'][str(n)]['region_lines_seen']} region "
              f"lines seen, {info['processes_measured']} processes", flush=True)
    per, missing = {}, {}
    total = covered = 0
    for k, lines in exe.items():
        got = [ln for ln in lines if any(ln in seen_by[n] for n in seen_by if n != 4 or k in NAMED)]
        per[k] = {"executable": len(lines), "covered": len(got)}
        miss = [ln for ln in lines if ln not in got]
        if miss:
            missing[k] = miss
        total += len(lines)
        covered += len(got)
    res["functions"] = per
    res["missing"] = missing
    res["executable_lines"] = total
    res["covered_lines"] = covered
    res["G_COVER"] = round(covered / total, 6) if total else None
    res["verdict"] = "PASS" if covered == total and passes == [1, 2, 3, 4] else ("FAIL" if covered < total else "PARTIAL")
    res["seconds"] = round(time.monotonic() - t0, 1)
    if _opt("--out"):
        json.dump(res, open(_opt("--out"), "w"), indent=1)
    print(json.dumps({k: res[k] for k in ("python", "executable_lines", "covered_lines", "G_COVER", "verdict")}),
          json.dumps(missing)[:1500])
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except v5f_tmp.DiskLow as e:
        sys.exit(v5f_tmp.stop_disk_low(e))
    finally:
        v5f_tmp.cleanup()
