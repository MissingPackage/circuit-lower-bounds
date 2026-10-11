"""SAT-side stability constraints (GHKK Definitions 1 and 2) on the free output truth-table variables
enc.fv[o, t] of an encoder.Enc built with an integer `outs` (free-function search).

Row convention (WP1): row t assigns x_{i+1} = (t >> i) & 1, so variable index i in 0..n-1 is bit i of t.

m_stable(enc, m, signs): Definition 2 -- for every Y, |Y| <= m+1, and every y in Y there is an assignment
    tau to X \\ Y such that g|tau == y (sign 'pos') or g|tau == not y (sign 'neg').  Encoded exactly as
    written (all sizes 1..m+1 of Y; the smaller sizes are implied by size m+1 when n >= m+1 but are kept).
weakly_m_stable(enc, m): Definition 1 -- for every Y, |Y| <= m, there are tau0, tau1 to X \\ Y with
    g|tau0 == 0 and g|tau1 == 1 (sizes 0..m of Y).
essential(enc): every input variable is essential for the function.
Each "there exists tau" is an OR over selector variables; each selector implies the 2^|Y| row equalities.
"""
from itertools import combinations, product


def _rows(n, fixed_vars, fixed_vals, free_vars):
    """all rows t consistent with the assignment fixed_vars <- fixed_vals, enumerated over free_vars.
    yields (t, dict free var -> bit)."""
    base = sum(b << v for v, b in zip(fixed_vars, fixed_vals))
    for ys in product((0, 1), repeat=len(free_vars)):
        t = base + sum(b << v for v, b in zip(free_vars, ys))
        yield t, dict(zip(free_vars, ys))


def m_stable(enc, m, signs=('pos', 'neg'), o=0):
    n = enc.n
    cnt = 0
    for size in range(1, min(m + 1, n) + 1):
        for Y in combinations(range(n), size):
            rest = [v for v in range(n) if v not in Y]
            for y in Y:
                sels = []
                for tau in product((0, 1), repeat=len(rest)):
                    for sg in signs:
                        a = enc._new(); sels.append(a); cnt += 1
                        for t, ys in _rows(n, rest, tau, Y):
                            want = ys[y] ^ (sg == 'neg')
                            f = enc.fv[o, t]
                            enc.cl.append([-a, f if want else -f])
                enc.cl.append(sels)
    return cnt


def weakly_m_stable(enc, m, o=0):
    n = enc.n
    cnt = 0
    for size in range(0, min(m, n) + 1):
        for Y in combinations(range(n), size):
            rest = [v for v in range(n) if v not in Y]
            for c in (0, 1):
                sels = []
                for tau in product((0, 1), repeat=len(rest)):
                    a = enc._new(); sels.append(a); cnt += 1
                    for t, _ in _rows(n, rest, tau, Y):
                        f = enc.fv[o, t]
                        enc.cl.append([-a, f if c else -f])
                enc.cl.append(sels)
    return cnt


def essential(enc, o=0):
    n = enc.n
    cnt = 0
    for i in range(n):
        sels = []
        for t in range(enc.R):
            if (t >> i) & 1:
                continue
            d = enc._new(); sels.append(d); cnt += 1
            f0, f1 = enc.fv[o, t], enc.fv[o, t | (1 << i)]
            enc.cl.append([-d, f0, f1])
            enc.cl.append([-d, -f0, -f1])
        enc.cl.append(sels)
    return cnt


def add_variant(enc, variant, essential_inputs=False):
    """variant in {stable1, stable1pos, weak1, stable2}; returns number of auxiliary variables added."""
    if variant == 'stable1':
        c = m_stable(enc, 1)
    elif variant == 'stable1pos':
        c = m_stable(enc, 1, signs=('pos',))
    elif variant == 'stable2':
        c = m_stable(enc, 2)
    elif variant == 'weak1':
        c = weakly_m_stable(enc, 1)
    else:
        raise ValueError(variant)
    if essential_inputs:
        c += essential(enc)
    return c
