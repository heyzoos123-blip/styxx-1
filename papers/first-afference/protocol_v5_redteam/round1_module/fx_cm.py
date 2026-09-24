class K:
    @classmethod
    def make(cls): return cls()
    def __call__(self): return 7
def boom(): raise ValueError("x")
def rec(n): return 0 if n == 0 else rec(n - 1)
