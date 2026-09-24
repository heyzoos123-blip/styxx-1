import functools
@functools.singledispatch
def process(x): return ("generic", x)
@process.register
def _(x: int): return ("int", x)
