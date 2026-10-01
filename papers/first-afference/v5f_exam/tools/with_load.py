"""with_load.py: run one exam command and record the machine load around it (the coordinator's rule while other
studies share the machine: a reviewer must see which results were taken under load).

  python tools/with_load.py [--max-load 4] [--out RESULT.json] [--log results_v5f/load_log.jsonl] -- CMD ...

With --max-load, the command starts only when the 1-min and 5-min load averages are both below it (the wait is
logged). The 1-min load average is sampled every 30 s while the command runs. On exit, if --out names a JSON
object the command wrote, a "load_average" key is added to it: {"before", "after", "samples_1min" (min, median,
max, n), "max_load_held", "started", "seconds"}; the same record, with the command and the exit status, is appended
to the log. The command's own stdout and stderr pass through. The runner, the sweeps and the gates are unchanged:
the record is this wrapper's, not theirs."""
import json, os, statistics, subprocess, sys, threading, time

argv = list(sys.argv[1:])
opts, cmd = {}, None
i = 0
while i < len(argv):
    if argv[i] == "--":
        cmd = argv[i + 1:]
        break
    if argv[i].startswith("--"):
        opts[argv[i]] = argv[i + 1]
        i += 2
    else:
        i += 1
if not cmd:
    print(__doc__)
    sys.exit(2)
max_load = float(opts["--max-load"]) if "--max-load" in opts else None
out = opts.get("--out")
log = opts.get("--log", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results_v5f", "load_log.jsonl"))


def la():
    try:
        return [round(x, 2) for x in os.getloadavg()]
    except (AttributeError, OSError):
        return None


waited = 0
while max_load is not None:
    x = la()
    if x is None or (x[0] < max_load and x[1] < max_load):
        break
    if waited % 300 == 0:
        print(f"with_load: load {x} at or above {max_load}; waiting", file=sys.stderr, flush=True)
    time.sleep(30)
    waited += 30
samples, stop = [], threading.Event()


def sample():
    while not stop.wait(30):
        x = la()
        if x:
            samples.append(x[0])


threading.Thread(target=sample, daemon=True).start()
before, t0, started = la(), time.monotonic(), time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
rc = subprocess.call(cmd)
stop.set()
rec = {"before": before, "after": la(),
       "samples_1min": ({"min": min(samples), "median": statistics.median(samples), "max": max(samples), "n": len(samples)}
                        if samples else None),
       "max_load_held": max_load, "waited_s": waited, "started": started, "seconds": round(time.monotonic() - t0, 1)}
if out and os.path.exists(out):
    try:
        d = json.load(open(out))
        if isinstance(d, dict):
            d["load_average"] = rec
            json.dump(d, open(out, "w"), indent=1)
    except (OSError, ValueError):
        pass
try:
    os.makedirs(os.path.dirname(log), exist_ok=True)
    with open(log, "a") as fh:
        fh.write(json.dumps({"cmd": cmd, "out": out, "rc": rc, **rec}) + "\n")
except OSError:
    pass
sys.exit(rc)
