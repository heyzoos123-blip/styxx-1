import time
def f(): return 1
def g(): return 2
def slow_then_g(delay=0.2):
    time.sleep(delay); return g()
async def af(): return f()
def gen():
    yield g()
