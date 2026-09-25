#!/bin/sh
# s1 stress matrix: both interpreters, rev 2 and rev 3, three modes, three seeds, 200 rounds of 50 ms each.
cd "$(dirname "$0")"
for v in 3.12 3.13; do for rv in 2 3; do for m in clean fault-nodead fault; do for seed in 1 2 3; do
  timeout 900 ../../rt3/venv$v/bin/python s1_unwind_stress.py $rv $m 200 $seed
done; done; done; done
