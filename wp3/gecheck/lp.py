"""Exact LP of FGHK rev. 2 (eq. (3) and Corollary 3.2.1, PDF p.15) over a set of
substitution types (WP3.1, pre-registration P4).

maximise  delta - aT/2 - aI   s.t.  delta - aI <= term_k  for every type k in the set,
          0 <= aT <= 1/4, aQ >= 0, aI >= 0, beta = 1 - 4 aT.
Per-substitution terms (type bound minus aI, two-substitution types halved):
  1: aI/2   2: aI   3: 4 beta   4: 3 + aT   5: 5 beta - aQ   6: 2.5 beta + aQ/2
  7: 2 beta + aQ
Solved exactly by vertex enumeration in rational arithmetic; cross-checked by a
grid search (numpy).  Usage: python -m gecheck.lp
"""
import itertools
import json
import sys
from fractions import Fraction as F

# variables: (aT, aQ, aI, u) with u = delta - aI; constraint rows a.v <= b
TERMS = {
    1: ((0, 0, F(1, 2)), 0),
    2: ((0, 0, 1), 0),
    3: ((-16, 0, 0), 4),
    4: ((1, 0, 0), 3),
    5: ((-20, -1, 0), 5),
    6: ((-10, F(1, 2), 0), F(5, 2)),
    7: ((-8, 1, 0), 2),
}
BIG = F(1000)


def constraints(types):
    rows = []
    for k in types:
        (cT, cQ, cI), c0 = TERMS[k]
        # u - cT aT - cQ aQ - cI aI <= c0
        rows.append(((F(-cT), F(-cQ), F(-cI), F(1)), F(c0), 'type %d' % k))
    rows += [((F(-1), 0, 0, 0), F(0), 'aT >= 0'), ((F(1), 0, 0, 0), F(1, 4), 'aT <= 1/4'),
             ((0, F(-1), 0, 0), F(0), 'aQ >= 0'), ((0, F(1), 0, 0), BIG, 'aQ <= BIG'),
             ((0, 0, F(-1), 0), F(0), 'aI >= 0'), ((0, 0, F(1), 0), BIG, 'aI <= BIG'),
             ((0, 0, 0, F(-1)), BIG, 'u >= -BIG')]
    return [(tuple(F(x) for x in a), F(b), nm) for a, b, nm in rows]


def solve4(A, b):
    M = [list(A[i]) + [b[i]] for i in range(4)]
    for c in range(4):
        p = next((r for r in range(c, 4) if M[r][c] != 0), None)
        if p is None:
            return None
        M[c], M[p] = M[p], M[c]
        for r in range(4):
            if r != c and M[r][c] != 0:
                f = M[r][c] / M[c][c]
                M[r] = [x - f * y for x, y in zip(M[r], M[c])]
    return [M[i][4] / M[i][i] for i in range(4)]


def objective(v):
    aT, aQ, aI, u = v
    return u - aT / 2


def solve(types):
    rows = constraints(types)
    best, arg, tight = None, None, None
    for idx in itertools.combinations(range(len(rows)), 4):
        v = solve4([rows[i][0] for i in idx], [rows[i][1] for i in idx])
        if v is None:
            continue
        if all(sum(a * x for a, x in zip(r[0], v)) <= r[1] for r in rows):
            o = objective(v)
            if best is None or o > best or (o == best and v[0] < arg[0]):
                best, arg = o, v
    tight = [r[2] for r in rows if sum(a * x for a, x in zip(r[0], arg)) == r[1]]
    return best, arg, tight


def grid(types, nT=1075, nQ=2000, qmax=5.0):
    import numpy as np
    aT = np.linspace(0, 0.25, nT + 1)[:, None]
    aQ = np.linspace(0, qmax, nQ + 1)[None, :]
    beta = 1 - 4 * aT
    terms = {3: 4 * beta + 0 * aQ, 4: 3 + aT + 0 * aQ, 5: 5 * beta - aQ,
             6: 2.5 * beta + aQ / 2, 7: 2 * beta + aQ}
    u = np.full((nT + 1, nQ + 1), np.inf)
    for k in types:
        if k in terms:
            u = np.minimum(u, terms[k])
    obj = u - aT / 2          # aI taken large enough: types 1, 2 are then slack
    i, j = np.unravel_index(np.argmax(obj), obj.shape)
    return float(obj[i, j]), float(aT[i, 0]), float(aQ[0, j])


def report(name, types, target=None):
    best, arg, tight = solve(types)
    aT, aQ, aI, u = arg
    g = grid(types)
    row = {'variant': name, 'types': sorted(types), 'optimum': str(best), 'optimum_float': float(best),
           'aT': str(aT), 'aQ': str(aQ), 'aI_min': str(2 * u) if 1 in types else str(aI),
           'delta_minus_aI': str(u), 'tight': tight, 'grid_optimum': g[0], 'grid_aT': g[1], 'grid_aQ': g[2]}
    if target is not None:
        row['target'] = str(target)
        row['equals_target'] = (best == target)
    print(json.dumps(row))
    return row


if __name__ == '__main__':
    out = []
    out.append(report('P4a full FGHK LP (types 1-7)', [1, 2, 3, 4, 5, 6, 7], F(3) + F(1, 86)))
    out.append(report('P4a eq. (3) as printed (types 1,3,4,5,6,7)', [1, 3, 4, 5, 6, 7], F(3) + F(1, 86)))
    out.append(report('P4b restricted to types 1,2,3,4,7', [1, 2, 3, 4, 7], F(3) + F(1, 34)))
    if len(sys.argv) > 1:
        types = sorted(set(int(t) for t in sys.argv[1].split(',')))
        out.append(report('certified types of Cases 1-5: %s' % types, types))
    if len(sys.argv) > 2:
        with open(sys.argv[2], 'w') as f:
            json.dump(out, f, indent=1)
