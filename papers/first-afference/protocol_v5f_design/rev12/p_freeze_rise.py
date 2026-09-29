# rev12 (GAP-38, GAP-39): what raises gc.get_freeze_count() with no gc.freeze() call, on 3.12.3 and 3.13.12,
# and whether objects made after the unfreeze become invisible to gc.get_referrers (really frozen).
import gc, sys
print(sys.version.split()[0], "boot count", gc.get_freeze_count())
gc.unfreeze(); print("after unfreeze", gc.get_freeze_count())
class C: pass
new = C(); holder = [new]                         # a tracked object made after the unfreeze, referenced by a list
gc.collect(0); print("after collect(0)", gc.get_freeze_count())
gc.collect(1); print("after collect(1)", gc.get_freeze_count())
gc.collect(); print("after collect()", gc.get_freeze_count())
print("new object's referrer still visible:", any(r is holder for r in gc.get_referrers(new)))
gc.unfreeze(); print("unfreeze again", gc.get_freeze_count()); gc.collect(); print("collect() again", gc.get_freeze_count())
gc.freeze(); n = gc.get_freeze_count(); gc.unfreeze(); gc.collect(); print("after freeze/unfreeze/collect", n, "->", gc.get_freeze_count())
