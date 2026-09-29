#!/bin/sh
# Re-run the exam author's receipts. Usage: tools/rerun.sh PY312 PY313 [PY310 PY311]
# Run from papers/first-afference/v5f_exam/. Writes nothing into the repository except where noted.
set -e
cd "$(dirname "$0")/.."
P12=$1; P13=$2; P10=$3; P11=$4
for P in "$P12" "$P13"; do "$P" smoke_cases.py | tail -1; "$P" tools/lint_region.py ref_v5f.py; done
for P in "$P10" "$P11"; do [ -n "$P" ] && "$P" smoke_cases.py | tail -1; done
python3 tools/mutants_v5f.py "$P12" "$P13"
# rules_v5f.json (revision 12): extract to a scratch file, reconcile, compare with the committed file
TMP=$(mktemp -d)
python3 tools/extract_rules.py "$TMP/atoms.json" >/dev/null
git show 78895e18:papers/first-afference/v5f_exam/rules_v5f.json > "$TMP/rules_rev11.json"
cp rules_v5f.json "$TMP/committed.json"
python3 tools/reconcile12.py "$TMP/atoms.json" "$TMP/rules_rev11.json" --write > "$TMP/counts.json"
if cmp -s rules_v5f.json "$TMP/committed.json"; then echo "rules_v5f.json: reproduced"; else echo "rules_v5f.json: DIFFERS"; cp "$TMP/committed.json" rules_v5f.json; fi
# v5e_port.py (revision 11, GAP-37): regenerated from the frozen v5e runner
python3 tools/gen_v5e_port.py --check
# the runner: tools/runner_mutants_v5f.py "$P12" "$P13" runs every weakening against the runner (long)
