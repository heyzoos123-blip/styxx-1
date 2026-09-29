#!/bin/sh
# Runs the exam author's smoke_cases.py against build.py's ref9.py (ref_v5f.py with C1-C3 applied).
# usage: sh run_smoke_ref9.sh <dir holding build.py's output>; nothing is written into the repository.
S=/tmp/claude-0/-home-user/1230efe6-3e44-5eb6-ad91-35910fea5db9/scratchpad/rt3
B=${1:?build dir}; W=$(mktemp -d)
cp "$(dirname "$0")/../../v5f_exam/smoke_cases.py" "$W/"; cp "$B/ref9.py" "$W/ref_v5f.py"
for v in 3.12 3.13; do (cd "$W" && $S/venv$v/bin/python smoke_cases.py 2>&1 | tail -1); done
