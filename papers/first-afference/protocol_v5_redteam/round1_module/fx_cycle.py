def f(): return 1
f.__wrapped__ = f          # e.g. a sloppy self-referential wrapper
