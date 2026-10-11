"""Independent brute-force checker for GHKK stability (Definitions 1 and 2).  Shares no code with
encoder.py / stability.py / simulate.py: a function is an integer whose bit t is the value on row t
(row t assigns x_{i+1} = (t >> i) & 1), restrictions are mask-and-compare on that integer, and circuits
are simulated with bit-parallel word operations.

  is_m_stable(tt, k, m, signs)      Definition 2, every Y with 1 <= |Y| <= m+1, every y in Y
  is_weakly_m_stable(tt, k, m)      Definition 1, every Y with 0 <= |Y| <= m
  essential_vars(tt, k)             variables the function depends on
  circuit_tt(circ)                  truth table (integer) of a decoded circuit, bit-parallel
  count(k, variant, essential)      exhaustive count over all 2^(2^k) functions

usage: stable_check.py check --k K (--tt INT | --circuit JSON) [--variant V] [--essential]
       stable_check.py count --k K --variant V [--essential]
       stable_check.py controls
exit status of `check`: 0 = property holds, 1 = property fails, 2 = usage error.
"""
import sys, json, argparse, itertools, time

VARIANTS = ('stable1', 'stable1pos', 'weak1', 'stable2')


def var_mask(k, i):
    """integer whose bit t is x_{i+1}(t) = (t >> i) & 1"""
    return sum(1 << t for t in range(1 << k) if (t >> i) & 1)


def rows_mask(k, fixed):
    """mask of rows consistent with the assignment fixed (dict var index -> bit)"""
    m = 0
    for t in range(1 << k):
        if all(((t >> v) & 1) == b for v, b in fixed.items()):
            m |= 1 << t
    return m


def _stable_tests(k, m, signs):
    """list over (Y, y) of lists of (mask, pattern): the (Y,y) requirement holds iff some
    (f & mask) == pattern."""
    tests = []
    for size in range(1, min(m + 1, k) + 1):
        for Y in itertools.combinations(range(k), size):
            rest = [v for v in range(k) if v not in Y]
            for y in Y:
                alts = []
                for tau in itertools.product((0, 1), repeat=len(rest)):
                    M = rows_mask(k, dict(zip(rest, tau)))
                    xy = var_mask(k, y) & M
                    if signs in ('both', 'pos'):
                        alts.append((M, xy))
                    if signs in ('both', 'neg'):
                        alts.append((M, M & ~xy))
                tests.append(alts)
    return tests


def _weak_tests(k, m):
    tests = []
    for size in range(0, min(m, k) + 1):
        for Y in itertools.combinations(range(k), size):
            rest = [v for v in range(k) if v not in Y]
            masks = [rows_mask(k, dict(zip(rest, tau))) for tau in itertools.product((0, 1), repeat=len(rest))]
            tests.append([(M, 0) for M in masks])        # some tau0 with g == 0 on Y
            tests.append([(M, M) for M in masks])        # some tau1 with g == 1 on Y
    return tests


def _holds(tt, tests):
    return all(any((tt & M) == P for M, P in alts) for alts in tests)


def is_m_stable(tt, k, m, signs='both'):
    return _holds(tt, _stable_tests(k, m, signs))


def is_weakly_m_stable(tt, k, m):
    return _holds(tt, _weak_tests(k, m))


def essential_vars(tt, k):
    full = (1 << (1 << k)) - 1
    ess = []
    for i in range(k):
        xi = var_mask(k, i)
        # value with x_i flipped: rows with x_i=0 take the value of row t | bit, and vice versa
        hi = (tt & xi) >> (1 << i)
        lo = (tt & ~xi & full) << (1 << i)
        flipped = (hi | lo) & full
        if flipped != tt:
            ess.append(i)
    return ess


def circuit_tt(circ):
    """bit-parallel simulation of {n, gates:[[j,k,[f00,f01,f10,f11]],...], outputs:[v]} -> integer tt of output 0"""
    n = circ['n']
    full = (1 << (1 << n)) - 1
    vals = [var_mask(n, i) for i in range(n)]
    for j, kk, f in circ['gates']:
        a, b = vals[j], vals[kk]
        na, nb = ~a & full, ~b & full
        v = 0
        if f[0]: v |= na & nb
        if f[1]: v |= na & b
        if f[2]: v |= a & nb
        if f[3]: v |= a & b
        vals.append(v)
    return vals[circ['outputs'][0]]


def tests_for(variant, k):
    if variant == 'stable1':
        return _stable_tests(k, 1, 'both')
    if variant == 'stable1pos':
        return _stable_tests(k, 1, 'pos')
    if variant == 'stable2':
        return _stable_tests(k, 2, 'both')
    if variant == 'weak1':
        return _weak_tests(k, 1)
    raise ValueError(variant)


def holds(tt, k, variant, essential=False):
    if essential and len(essential_vars(tt, k)) != k:
        return False
    return _holds(tt, tests_for(variant, k))


def count(k, variant, essential=False):
    tests = tests_for(variant, k)
    c = 0
    ex = []
    for tt in range(1 << (1 << k)):
        if _holds(tt, tests) and (not essential or len(essential_vars(tt, k)) == k):
            c += 1
            if len(ex) < 4:
                ex.append(tt)
    return c, ex


def report(tt, k):
    return dict(k=k, tt=tt, ones=bin(tt).count('1'), essential=essential_vars(tt, k),
                stable1=is_m_stable(tt, k, 1), stable1pos=is_m_stable(tt, k, 1, 'pos'),
                weak1=is_weakly_m_stable(tt, k, 1), stable2=is_m_stable(tt, k, 2),
                weak2=is_weakly_m_stable(tt, k, 2))


def _tt_of(k, g):
    return sum(int(bool(g([(t >> i) & 1 for i in range(k)]))) << t for t in range(1 << k))


CONTROLS = [
    ('MAJ_5', 5, lambda x: sum(x) >= 3), ('XOR_5', 5, lambda x: sum(x) % 2),
    ('THR1_5', 5, lambda x: sum(x) >= 1), ('THR2_5', 5, lambda x: sum(x) >= 2),
    ('THR3_5', 5, lambda x: sum(x) >= 3), ('THR4_5', 5, lambda x: sum(x) >= 4), ('THR5_5', 5, lambda x: sum(x) >= 5),
    ('MOD3_5_0', 5, lambda x: sum(x) % 3 == 0), ('MOD3_5_1', 5, lambda x: sum(x) % 3 == 1), ('MOD3_5_2', 5, lambda x: sum(x) % 3 == 2),
    ('MAJ_3', 3, lambda x: sum(x) >= 2), ('MUX_3', 3, lambda x: x[1] if x[0] else x[2]),
    ('x1x2+x3x4', 4, lambda x: (x[0] & x[1]) ^ (x[2] & x[3])),
    ('x1x2+x3x4x5', 5, lambda x: (x[0] & x[1]) ^ (x[2] & x[3] & x[4])),
    ('x1x2x3+x4x5x6', 6, lambda x: (x[0] & x[1] & x[2]) ^ (x[3] & x[4] & x[5])),
    ('MUX_3+dummy x4', 4, lambda x: x[1] if x[0] else x[2]),
    ('gst1', 5, None),
]
GST1 = [0,0,0,0,0,0,1,1,0,1,0,1,1,1,1,0,0,1,1,1,0,1,1,0,0,1,1,0,1,0,0,0]   # GHKK Lemma 4, index a = sum x_i 2^i


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['check', 'count', 'controls'])
    ap.add_argument('--k', type=int); ap.add_argument('--tt', type=int); ap.add_argument('--circuit')
    ap.add_argument('--variant', default='stable1'); ap.add_argument('--essential', action='store_true')
    a = ap.parse_args()
    if a.cmd == 'controls':
        for name, k, g in CONTROLS:
            tt = sum(b << i for i, b in enumerate(GST1)) if g is None else _tt_of(k, g)
            print(name, report(tt, k))
        return 0
    if a.cmd == 'count':
        t0 = time.time(); c, ex = count(a.k, a.variant, a.essential)
        print(f'count k={a.k} variant={a.variant} essential={int(a.essential)} total={1 << (1 << a.k)} '
              f'holds={c} examples={ex} elapsed_s={time.time() - t0:.1f}')
        return 0
    if a.circuit:
        circ = json.loads(a.circuit); k = circ['n']; tt = circuit_tt(circ)
    elif a.tt is not None and a.k:
        k, tt = a.k, a.tt
    else:
        print('need --k and --tt, or --circuit'); return 2
    r = report(tt, k); ok = holds(tt, k, a.variant, a.essential)
    print(json.dumps(dict(variant=a.variant, essential_required=a.essential, verdict='accept' if ok else 'reject', **r)))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
