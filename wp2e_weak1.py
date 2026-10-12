"""WP2e: brute-force checker for weak 1-stability (GHKK Definition 1 with m = 1, PDF p.8),
written from the definition and sharing no code with stable_check.py.

Definition 1 (m = 1): g(X) is weakly 1-stable if for every Y subseteq X with |Y| <= 1 there
exist tau_0, tau_1 : X \\ Y -> {0,1} such that g restricted by tau_0 is the constant 0 on Y and
g restricted by tau_1 is the constant 1 on Y.  |Y| = 0 is included (g takes both values).

Truth-table convention (same integers as the rest of the repository): bit t of the integer is
g on row t, and row t assigns x_{i+1} = (t >> i) & 1.  Here the integer is only ever read through
value(tt, assignment), one row at a time; no masks.

usage: wp2e_weak1.py check --k K --tt INT     exit 0 = weakly 1-stable, 1 = not, 2 = usage error
       wp2e_weak1.py validate                 V1 (MAJ_3, MUX_3 accept; XOR_3, AND_3 reject) and
                                              V2 (agreement with stable_check weak1, all k = 3, 4)
"""
import sys, json, argparse, itertools, time


def value(tt, assignment):
    """g at the assignment (tuple of bits, assignment[i] = x_{i+1})"""
    row = 0
    for i, b in enumerate(assignment):
        if b:
            row += 2 ** i
    return (tt >> row) & 1


def restricted_values(tt, k, Y, tau):
    """set of values of g over all completions of tau (dict var -> bit) on the variables Y"""
    vals = set()
    for ys in itertools.product((0, 1), repeat=len(Y)):
        a = [None] * k
        for v, b in tau.items():
            a[v] = b
        for v, b in zip(Y, ys):
            a[v] = b
        vals.add(value(tt, a))
    return vals


def weak1_witnesses(tt, k):
    """dict Y -> (tau_0, tau_1) for every Y with |Y| <= 1, or None if some Y has no witness pair.
    Y is a tuple of variable indices (0-based); tau is a dict over the remaining variables."""
    out = {}
    for size in (0, 1):
        for Y in itertools.combinations(range(k), size):
            rest = [v for v in range(k) if v not in Y]
            tau0 = tau1 = None
            for bits in itertools.product((0, 1), repeat=len(rest)):
                tau = dict(zip(rest, bits))
                vals = restricted_values(tt, k, Y, tau)
                if vals == {0} and tau0 is None:
                    tau0 = tau
                if vals == {1} and tau1 is None:
                    tau1 = tau
                if tau0 is not None and tau1 is not None:
                    break
            if tau0 is None or tau1 is None:
                return None
            out[Y] = (tau0, tau1)
    return out


def is_weak1(tt, k):
    return weak1_witnesses(tt, k) is not None


def tt_of(k, fn):
    return sum(int(bool(fn([(t >> i) & 1 for i in range(k)]))) << t for t in range(1 << k))


CONTROLS = [  # name, k, function, expected verdict
    ('MAJ_3', 3, lambda x: x[0] + x[1] + x[2] >= 2, True),
    ('MUX_3', 3, lambda x: x[1] if x[0] else x[2], True),
    ('XOR_3', 3, lambda x: x[0] ^ x[1] ^ x[2], False),
    ('AND_3', 3, lambda x: x[0] & x[1] & x[2], False),
]


def validate():
    ok = True
    for name, k, fn, want in CONTROLS:
        tt = tt_of(k, fn)
        w = weak1_witnesses(tt, k)
        got = w is not None
        print(f'V1 {name} tt={tt} verdict={"accept" if got else "reject"} expected={"accept" if want else "reject"} '
              f'{"ok" if got == want else "FAIL"}')
        if w:
            print('   witnesses', {str(Y): w[Y] for Y in w})
        ok &= got == want
    import stable_check
    for k in (3, 4):
        t0 = time.time()
        tests = stable_check.tests_for('weak1', k)
        dis, pos = [], 0
        for tt in range(1 << (1 << k)):
            a = is_weak1(tt, k)
            b = stable_check._holds(tt, tests)
            pos += a
            if a != b:
                dis.append(tt)
        print(f'V2 k={k} functions={1 << (1 << k)} weak1_new={pos} disagreements_with_stable_check={len(dis)} '
              f'{dis[:10]} elapsed_s={time.time() - t0:.1f}')
        ok &= not dis
    print('validate', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['check', 'validate'])
    ap.add_argument('--k', type=int); ap.add_argument('--tt', type=int)
    a = ap.parse_args()
    if a.cmd == 'validate':
        return validate()
    if a.k is None or a.tt is None:
        print('need --k and --tt'); return 2
    w = weak1_witnesses(a.tt, a.k)
    print(json.dumps(dict(k=a.k, tt=a.tt, verdict='accept' if w else 'reject',
                          witnesses={str(Y): w[Y] for Y in w} if w else None)))
    return 0 if w else 1


if __name__ == '__main__':
    sys.exit(main())
