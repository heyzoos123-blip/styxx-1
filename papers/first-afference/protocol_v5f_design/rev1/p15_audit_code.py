# X92b / X133: an audit hook sees each function __code__ write, with the new code as argument,
# so a fault can be placed exactly at the restore write.
import sys
seen = []
def hook(ev, args):
    if ev == 'object.__setattr__' and len(args) >= 2 and args[1] == '__code__': seen.append(args[2] is ORIG)
sys.addaudithook(hook)
def f(): pass
ORIG = f.__code__
f.__code__ = ORIG.replace()   # mint
f.__code__ = ORIG             # restore
print(sys.version.split()[0], 'audit object.__setattr__ __code__ events (value is original):', seen)
