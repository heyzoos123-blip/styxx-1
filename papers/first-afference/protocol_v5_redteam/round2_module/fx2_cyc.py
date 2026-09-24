def _make(limit):
    def walk(n):                 # a recursive closure: walk -> cell -> walk is a reference cycle
        return 0 if n >= limit else 1 + walk(n + 1)
    return walk
walk10 = _make(10)
def warmup():                    # builds and drops a temporary walker
    w = _make(3); w(0)
warmup()
