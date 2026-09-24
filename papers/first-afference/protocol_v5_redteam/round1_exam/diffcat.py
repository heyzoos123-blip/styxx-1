import sys, json, collections, re
sys.argv=['x','--attempt-b']
sys.path.insert(0,'papers/first-afference')
import run_protocol_v5 as R
v4=R._pinned_v4()
from pathlib import Path
rows=[]
for res_file in sorted(R.ROOT.glob("papers/*/*_result.json")):
    try: d=json.loads(res_file.read_text())
    except Exception: continue
    if not isinstance(d,dict) or not isinstance(d.get('prereg'),str): continue
    p=res_file.parent/d['prereg']
    if not p.is_file() or p.name in R.OWN_PREREGS: continue
    rows.append((res_file,p,d))
cat=collections.Counter(); scored=[]
for rf,p,d in rows:
    o4=R._outcome(v4.Experiment,p,d); o5=R._outcome(R.Experiment,p,d)
    assert o4==o5
    if o5.startswith('RAISED'):
        cat[re.sub(r"line \d+","line N",o5[:90])]+=1
    else:
        pc = 'prereg_commit' in d and 'gates' in d
        scored.append((rf.parent.name+'/'+rf.name, o5==d.get('verdict'), pc, o5[:50]))
print(len(rows))
for k,v in cat.most_common(): print(v,k)
print('scored',len(scored), 'match committed', sum(s[1] for s in scored), 'has keys', sum(s[2] for s in scored))
for s in scored:
    if not s[1] or not s[2]: print(s)
