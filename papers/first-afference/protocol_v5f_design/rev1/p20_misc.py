# (a)8: sys.setprofile is per-thread; (a)9: object_pairs_hook makes every level an OrderedDict
import sys, threading, json, collections
def prof(*a): pass
sys.setprofile(prof)
seen = []
t = threading.Thread(target=lambda: seen.append(sys.getprofile())); t.start(); t.join()
sys.setprofile(None)
print(sys.version.split()[0], 'profiler set on main, seen on a new thread:', seen[0])
r = json.loads('{"coverage_trace": {"tracer": "x"}}', object_pairs_hook=collections.OrderedDict)
print('outer is dict subclass:', issubclass(type(r), dict), '| has key:', 'coverage_trace' in r,
      '| inner type:', type(dict.get(r, 'coverage_trace')).__name__)
