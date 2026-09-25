# (b) last item: dict.get on a user dict whose stored key is a str subclass with a colliding hash
import sys
ran = []
class S(str):
    def __hash__(self): return hash('coverage_trace')
    def __eq__(self, o): ran.append('eq'); return str.__eq__(self, o)
d = {S('zzz'): 1}
print(sys.version.split()[0], dict.get(d, 'coverage_trace'), ran)
import json
j = json.loads('{"coverage_trace": {"a": 1}}')
print("json keys exact str:", all(type(k) is str for k in j))
