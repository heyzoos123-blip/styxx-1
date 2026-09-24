def plain(x): return x
def _mk():
    a = 1; b = 2; c = 3
    def clos(x): return x + a + b + c
    return clos
clos = _mk()
def _mk_big():
    big = list(range(10))
    def bigloc(x):
        l0=l1=l2=l3=l4=l5=l6=l7=l8=l9=l10=l11=l12=l13=l14=l15=l16=l17=l18=l19=x
        return x + big[0]
    return bigloc
bigloc = _mk_big()
