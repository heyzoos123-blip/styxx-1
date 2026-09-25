# (b) #2: is asyncio.run(main(), loop_factory=<eager>) main's first step run eagerly on the caller's stack?
import asyncio, sys
def where():
    names = []; f = sys._getframe(1)
    while f is not None: names.append(f.f_code.co_qualname); f = f.f_back
    return names
seen = {}
async def child():
    seen['child'] = where()
async def main():
    seen['main'] = where()
    t = asyncio.create_task(child())       # eager: runs its first step now, on main's stack
    await t
def factory():
    loop = asyncio.new_event_loop(); loop.set_task_factory(asyncio.eager_task_factory); return loop
def section():                              # stands for the section's fn
    return asyncio.run(main(), loop_factory=factory)
section()
for k, v in seen.items():
    print(sys.version.split()[0], k, 'Handle._run on chain:', 'Handle._run' in v, '| section on chain:', 'section' in v)
