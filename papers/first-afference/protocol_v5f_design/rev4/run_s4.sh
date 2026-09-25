#!/bin/sh
# s4 matrix: both interpreters; revisions 3 (as specified), 3s (revision 3 under a splitting instrument) and 4;
# three modes; three seeds; 100 rounds; with the Z (open-versus-own-exit) races, and without them (noz).
cd "$(dirname "$0")"
for v in 3.12 3.13; do for z in Z noz; do for rv in 3 3s 4; do for m in clean fault-nodead fault; do for seed in 1 2 3; do
  timeout 900 ../../rt3/venv$v/bin/python s4_stress.py $rv $m 100 $seed $z
done; done; done; done; done
