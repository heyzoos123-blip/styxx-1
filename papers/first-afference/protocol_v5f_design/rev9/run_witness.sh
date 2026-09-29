#!/bin/sh
# usage: sh run_witness.sh <dir holding build.py's output>; one fresh process per (version, module, case)
S=/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt3
B=${1:?build dir}
for v in 3.12 3.13; do
  for m in ref9 mut_gle_calltime mut_gle_nocheck mut_grl_nocheck; do
    for c in V69b V69c X156f X156g X156g_ctl; do
      printf '%s %s ' "$v" "$m"
      $S/venv$v/bin/python "$(dirname "$0")/witness.py" "$B/$m.py" $c 2>&1 | tail -1
    done
  done
done
