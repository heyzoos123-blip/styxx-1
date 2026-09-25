# (b)/(c) uvloop shape: a loop whose dispatch has no Python frame leaves no cut frame, but the
# running loop at the hit differs from the one when the section opened (None).
import asyncio, sys, operator
class CDispatchLoop(asyncio.SelectorEventLoop):
    """Runs ready handles' callbacks through C (map/operator.call), never through Handle._run."""
    def _run_once(self):
        ready = list(self._ready); self._ready.clear()
        list(map(lambda h: h._context.run(h._callback, *h._args), ready)) if False else \
            list(map(operator.call, [lambda h=h: h._context.run(h._callback, *h._args) for h in ready]))
        if not ready: super()._run_once()
seen = {}
def target():
    names = []; f = sys._getframe(1)
    while f is not None: names.append(f.f_code.co_qualname); f = f.f_back
    seen['chain'] = names
    seen['running_loop'] = asyncio.events._get_running_loop()
def section(loop):                          # stands for the section fn; its caller is the anchor
    seen['loop_at_open'] = asyncio.events._get_running_loop()
    loop.call_soon(target)                   # work queued "by someone else"
    loop.run_until_complete(asyncio.sleep(0.01))
def _run(fn, *a): return fn(*a)
loop = CDispatchLoop()
_run(section, loop)
ch = seen['chain']
print(sys.version.split()[0], 'Handle._run on chain:', 'Handle._run' in ch, '| anchor _run on chain:', '_run' in ch)
print('running loop at open:', seen['loop_at_open'], '| at the hit is the section loop:', seen['running_loop'] is loop)
print('_get_running_loop is C:', type(asyncio.events._get_running_loop).__name__)
