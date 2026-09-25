# #130279 on _run_async's await: on 3.12 the throw-path JUMP_BACKWARD after CLEANUP_THROW lies outside
# the try's exception-table range. An exception there (a signal at that back-edge) skips the finally.
# Sweep: every instruction offset, on both the send path and the throw-then-return path.
import dis, signal, sys
M = sys.monitoring; E = M.events; TOOL = 5
class Boom(Exception): pass
class Cancel(Exception): pass
FIN = []
class Awaitee:
    """Yields twice; a thrown Cancel is caught and it returns (the CLEANUP_THROW path)."""
    def __await__(self):
        try:
            yield None; yield None
        except Cancel:
            return 'cancelled-but-returned'
        return 7
async def afn():
    return await Awaitee()
async def _run_async(afn):
    end = "raised"
    try:
        result = await afn(); end = "returned"
    finally:
        FIN.append(end)
    return result
def drive_send(c):
    try:
        while True: c.send(None)
    except StopIteration as e: return e.value
def drive_throw(c):
    c.send(None)
    try: c.throw(Cancel)
    except StopIteration as e: return e.value
    return drive_send(c)
code = _run_async.__code__
M.use_tool_id(TOOL, 'probe')
ops = {i.offset: i.opname for i in dis.get_instructions(code)}
for name, drive in (('send path', drive_send), ('throw-then-return path', drive_throw)):
    skipped = []
    for off in sorted(ops):
        armed = [True]
        def cb(c, o, off=off):
            if armed[0] and c is code and o == off: armed[0] = False; raise Boom
        M.register_callback(TOOL, E.INSTRUCTION, cb); M.set_local_events(TOOL, code, E.INSTRUCTION)
        FIN.clear(); through = False
        try: drive(_run_async(afn))
        except Boom as e:
            tb = e.__traceback__
            while tb is not None:
                through |= tb.tb_frame.f_code is code; tb = tb.tb_next
        finally: M.set_local_events(TOOL, code, 0)
        # a genuine skip: raised in this frame at an offset of the try body (not in the finally itself)
        if through and not FIN and ops[off] not in ('RETURN_GENERATOR', 'POP_TOP', 'RESUME') and off > 10 and 'LOAD_GLOBAL' != ops[off]:
            skipped.append((off, ops[off]))
    print(sys.version.split()[0], name, 'finally SKIPPED at:', skipped)
