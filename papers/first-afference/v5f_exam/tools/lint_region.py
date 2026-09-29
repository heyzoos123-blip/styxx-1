"""Static checks on a reference or implementation file (exam author).
Usage: python tools/lint_region.py path/to/ref_v5f.py
  - no region code object has a nested code object (G_HYG MF4);
  - no backward jump in the step functions;
  - revision 10 (R9-4) G_HYG clause: in coverage_trace(), the _MON[0] and _get_running_loop
    assignments follow every raise and the import of asyncio, and precede the first _HANDLE_DICT use."""
import importlib.util, sys, dis, types
s=importlib.util.spec_from_file_location('ref_v5f', sys.argv[1]); m=importlib.util.module_from_spec(s); sys.modules['ref_v5f']=m; s.loader.exec_module(m)
fp = m._v5_faultpoints()
region = dict(fp)
region['Experiment._check_coverage']=m.Experiment._check_coverage.__code__
region['Experiment.check_metrics']=m.Experiment.check_metrics.__code__
region['Experiment.score']=m.Experiment.score.__code__
region['_check_trace_shape']=m._check_trace_shape.__code__
bad=[k for k,c in region.items() if any(isinstance(x, types.CodeType) for x in c.co_consts)]
print("nested code objects:", bad)
for k in ('_commit','_detach','_unwind_on','_unwind_off','_take','_register','_set_local','_named','_run'):
    back=[i.opname for i in dis.get_instructions(fp[k]) if 'BACKWARD' in i.opname]
    if back: print("backward jump in", k, back)
print("step back-edge check done")
ev = {'INSTRUCTION','LINE','JUMP','BRANCH','CALL','C_RETURN','C_RAISE','RAISE','PY_THROW','RERAISE','EXCEPTION_HANDLED','STOP_ITERATION'}
src=open(sys.argv[1]).read().split('# -- v5f: the coverage tracer')[1]
for e in ev:
    if 'events.'+e in src or ' '+e+' ' in src: print('event named', e)
for w in ('setprofile','settrace','threading.Lock','RLock',' with '):
    if w in src: print('found', repr(w))

import ast
t = ast.parse(open(sys.argv[1]).read())
f = [n for n in t.body if isinstance(n, ast.FunctionDef) and n.name == 'coverage_trace'][0]
raises = [n.lineno for n in ast.walk(f) if isinstance(n, ast.Raise)]
imp = [n.lineno for n in ast.walk(f) if isinstance(n, ast.Import) and any(a.name == 'asyncio' for a in n.names)]
binds = [n.lineno for n in ast.walk(f) if isinstance(n, ast.Assign) and any(
    (isinstance(x, ast.Subscript) and getattr(x.value, 'id', None) == '_MON') or getattr(x, 'id', None) == '_get_running_loop'
    for x in n.targets)]
hd = min(n.lineno for n in ast.walk(f) if isinstance(n, ast.Name) and n.id == '_HANDLE_DICT')
ok = binds and imp and all(max(raises) < x and imp[0] < x < hd for x in binds)
print("G_HYG R9-4 order:", "OK" if ok else "VIOLATION", {"last_raise": max(raises), "import_asyncio": imp, "binds": binds, "first_HANDLE_DICT": hd})
