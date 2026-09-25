# The class-B paragraph says one route is left and "that code is either" (a) a loop class whose own _run_once
# bypasses Handle._run or (b) a self-restoring _run_once replacement. A third shape needs neither: the section,
# opened in a task of a running loop, drains that loop's ready queue itself. Same loop, no cut frame: credited.
import sys, asyncio
sys.path.insert(0, __file__.rsplit('/', 2)[0] + '/rev2')
import mech2 as mech
def f(): return 1
def drain(L):
    while L._ready:
        h = L._ready.popleft()
        if not h._cancelled: h._context.run(h._callback, *h._args)
with mech.Tracer(f) as tr:
    async def other(): asyncio.get_running_loop().call_soon(f)        # another task schedules the job
    async def main():
        L = asyncio.get_running_loop()
        await asyncio.create_task(other())
        L.call_soon(f)
        tr.run('A', drain, L)
    asyncio.run(main())
r = tr.result(); print(sys.version.split()[0], 'manual _ready drain in a section:', r['calls'], 'dispatched', r['dispatched'])
