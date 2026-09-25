# (a)5 / S2: freeze count moves without freeze/unfreeze; unfreeze on 3.12.3
import gc, sys
print(sys.version.split()[0], 'boot', gc.get_freeze_count())
class C: pass
xs = [C() for _ in range(10)]
base = gc.get_freeze_count()
gc.freeze(); n = gc.get_freeze_count(); print('after freeze', n, 'increase', n - base)
del xs; print('after del of frozen objects', gc.get_freeze_count(), 'delta', gc.get_freeze_count() - n)
gc.unfreeze(); print('after unfreeze', gc.get_freeze_count())
