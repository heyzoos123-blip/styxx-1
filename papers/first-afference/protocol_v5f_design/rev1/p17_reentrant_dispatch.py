# X65c witness shape: a section opened inside a task of loop L re-enters L's dispatch
# (loop._run_once()), running a callback another task scheduled. The running loop is the same at
# open and at the hit, so only the Handle._run cut separates them.
import asyncio, sys
seen = {}
def f():
    names = []; fr = sys._getframe(1)
    while fr is not None: names.append(fr.f_code.co_qualname); fr = fr.f_back
    seen['chain'] = names; seen['loop_at_hit'] = asyncio.events._get_running_loop()
def section(loop):
    seen['loop_at_open'] = asyncio.events._get_running_loop()
    loop._run_once()                          # re-entrant dispatch inside the section
def _run(fn, *a): return fn(*a)               # anchor
async def other(): asyncio.get_running_loop().call_soon(f)
async def main():
    loop = asyncio.get_running_loop()
    await other()
    _run(section, loop)
asyncio.run(main())
ch = seen['chain']
i_h, i_a = ch.index('Handle._run'), ch.index('_run')
print(sys.version.split()[0], 'same loop at open and hit:', seen['loop_at_open'] is seen['loop_at_hit'],
      '| Handle._run met before the anchor:', i_h < i_a)
