#!/bin/sh
# Re-runs every revision-3 probe against the final mech3.py, both interpreters. Outputs: out_<probe>.txt
cd "$(dirname "$0")"
PY12=../../rt3/venv3.12/bin/python; PY13=../../rt3/venv3.13/bin/python
for p in q1_test_then_call_atomic c5r3_retire_step6_race c6r3_x143_placement c7r3_stale_unwind_after_open_fault c8r3_fresh_wrapper_per_case w1_rev3_witnesses; do
  o=out_$(echo $p | cut -d_ -f1).txt; : > $o
  for PY in $PY12 $PY13; do $PY $p.py >> $o 2>&1; done
done
python3 m1_unwind_modelcheck.py > out_m1.txt 2>&1
./run_s1.sh > out_s1.txt 2>&1
echo ALLDONE >> out_s1.txt
