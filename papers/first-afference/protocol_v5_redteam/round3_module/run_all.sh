#!/bin/sh
# usage: sh run_all.sh [python]   (t05 and t03b are slow; t04 is swept by argv)
P=${1:-python}
cd "$(dirname "$0")"
for s in t01_wraps_family.py t02_close_checks_bypassed.py t06_frame_identity.py t07_resolution_and_context.py t08_factory_products.py t12_asyncio_shared_worker.py t11_perf_closure.py; do echo "== $s"; timeout 120 $P $s 2>&1; done
echo "== t09 (needs tqdm in ./site)"; PYTHONPATH=./site timeout 60 $P t09_library_threads.py 2>/dev/null
echo "== t10"; timeout 120 $P t10_keyboardinterrupt.py 2>&1 | tail -2
echo "== t04 record-inside-trace deadlock sweep"; hung=""; for k in $(seq 1 40); do timeout 10 $P t04_finalizer_deadlock.py record $k 2>&1 | grep -q '^ok' || hung="$hung $k"; done; echo "non-ok k:$hung"
echo "== t03 signal timeout"; timeout 300 $P t03_signal_timeout_swallowed.py 2>&1
