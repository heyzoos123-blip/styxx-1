import sys, dis
M=sys.monitoring; E=M.events
def loop(n):
    i = 0
    while i < n:
        i += 1
    return i
offs=[]; lines=[]
def cb(code, off): offs.append(off)
def lcb(code, line): lines.append(line)
M.use_tool_id(1,'line'); M.register_callback(1, E.LINE, lcb); M.set_local_events(1, loop.__code__, E.LINE)
M.use_tool_id(5,'inj'); M.register_callback(5, E.INSTRUCTION, cb); M.set_local_events(5, loop.__code__, E.INSTRUCTION)
loop(3)
print(sys.version.split()[0], 'LINE+INSTRUCTION on two tools: instruction offsets seen', sorted(set(offs)), 'lines', sorted(set(lines)))
sys.settrace(lambda *a: None); offs.clear(); loop(3); sys.settrace(None)
print(sys.version.split()[0], 'plus settrace: instruction offsets seen', sorted(set(offs)))
