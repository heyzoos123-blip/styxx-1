# (b) L-WHERE / (c) R1-B3: under uvloop no Handle._run frame exists; the running-loop boundary still separates
import asyncio, sys, threading, uvloop
seen = {}
def chain():
    names = []; f = sys._getframe(2)
    while f is not None: names.append(f.f_code.co_qualname); f = f.f_back
    return names
def f_target():
    seen['chain'] = chain(); seen['loop_at_hit'] = asyncio.events._get_running_loop()
def section():                              # section fn: runs a loop serving another thread's job
    seen['loop_at_open'] = asyncio.events._get_running_loop()
    loop = uvloop.new_event_loop()
    def other_thread(): loop.call_soon_threadsafe(f_target)
    async def serve():
        threading.Thread(target=other_thread).start(); await asyncio.sleep(0.05)
    loop.run_until_complete(serve()); seen['loop'] = loop
def _run(fn): return fn()                   # stands for the anchor frame
_run(section)
ch = seen['chain']
print(sys.version.split()[0], 'uvloop', uvloop.__version__)
print('chain:', ch)
print('Handle._run on chain:', any('Handle._run' in c for c in ch), '| anchor on chain:', '_run' in ch)
print('loop at open None:', seen['loop_at_open'] is None, '| loop at hit is the uvloop loop:', seen['loop_at_hit'] is seen['loop'])
# a section opened inside a uvloop task: loop at open == loop at hit
async def main():
    seen['open2'] = asyncio.events._get_running_loop(); f_target(); seen['hit2'] = seen['loop_at_hit']
uvloop.run(main())
print('section inside a uvloop task: same loop at open and at hit:', seen['open2'] is seen['hit2'])
