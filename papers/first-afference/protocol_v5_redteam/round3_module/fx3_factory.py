def make_mul(k):
    return lambda x, k=k: x * k            # the classic default-binding idiom: no closure
double = make_mul(2)                       # declared: 'fx3_factory:double'

def make_scorer(metric, strict):
    def score(x, strict=strict):           # closure: metric; behaviour switch: a default
        v = metric(x)
        if strict and v < 0:
            raise ValueError("negative")
        return v
    return score
score_lenient = make_scorer(abs, False)    # declared: 'fx3_factory:score_lenient'
