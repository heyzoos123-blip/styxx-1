# N7: rev 1 builds the FOREIGN_DEFINITION name as dict.get(inner.__globals__, '__name__') + ':' + inner.__qualname__.
# For a function exec'd into a fresh namespace (no '__name__'), or one whose '__name__' is not a str, that raises
# TypeError out of __enter__. Rev 2: use the name only when type(name) is str, else co_filename.
import sys
ns = {}; exec('def fit(): return 1', ns); fn1 = ns['fit']                     # globals without __name__
ns2 = {'__name__': 42}; exec('def fit(): return 1', ns2); fn2 = ns2['fit']    # a non-str __name__
class S(str): pass
ns3 = {'__name__': S('mod')}; exec('def fit(): return 1', ns3); fn3 = ns3['fit']  # a str subclass
def rev1(inner): return dict.get(inner.__globals__, '__name__') + ':' + inner.__qualname__
def rev2(inner):
    name = dict.get(inner.__globals__, '__name__')
    return (name if type(name) is str else inner.__code__.co_filename) + ':' + inner.__qualname__
for label, fn in (('no __name__', fn1), ('__name__ = 42', fn2), ('__name__ a str subclass', fn3)):
    try: a = rev1(fn)
    except Exception as e: a = '%s: %s' % (type(e).__name__, e)
    print(sys.version.split()[0], '%-24s rev1 -> %-60s rev2 -> %s' % (label, a, rev2(fn)))
