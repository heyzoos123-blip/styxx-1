#!/bin/sh
cd "$(dirname "$0")"
for s in v1_round1.py a1_shared_after_entry.py a2_resolution.py a3_threads.py a4_concurrent_pool_falsepass.py a5_leaks.py a6_misc.py a6a_recursion_rootcause.py a7_malformed.py a9_threadpool_race.py a10_cyclic_garbage.py a11_grandchild.py; do echo "== $s"; timeout 120 python $s 2>&1; done
echo "== v1_b4_cprofile.py under -m cProfile"; python -m cProfile -o /dev/null v1_b4_cprofile.py 2>&1
