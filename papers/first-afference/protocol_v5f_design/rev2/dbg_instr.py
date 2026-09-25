import sys, dis
M=sys.monitoring; E=M.events
def loop(n):
    i = 0
    while i < n:
        i += 1
    return i
offs=[]
def cb(code, off): offs.append(off)
M.use_tool_id(5,'inj'); M.register_callback(5, E.INSTRUCTION, cb); M.set_local_events(5, loop.__code__, E.INSTRUCTION)
loop(3)
be=[i.offset for i in dis.get_instructions(loop) if i.opname.startswith('JUMP_BACKWARD')]
print(sys.version.split()[0], 'backedge offsets', be, 'instruction offsets seen', sorted(set(offs)))
