SM1 journal as a record (not used for sm1_result.json).

Made on revision 12's reference and runner, from 2026-09-30 to 2026-10-01, and stopped when revision 13 found
that the runner's importlib.reload re-imports the unpatched v5f_exam/ref_v5f.py under an SM1 patch (X156c,
X158e). sm1_journal_purged.json lists the entries removed before the resume after the disk filled: full-disk
failures, the 3.13.12 verdicts recorded near the first one, the crash rows run while the disk filled, the
3.12.3 G_FI reference pair made before the crash sweep's background-hang fix (c8dc6b09), and
A_txn_shared_succ's first row (re-run as HANG).
