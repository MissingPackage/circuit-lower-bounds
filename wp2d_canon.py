"""WP2d stage E helper: map a set of k-input truth tables (WP1 integers, k <= 6) to the canonical form
"minimum over all k! input permutations" (output sign untouched: both enumerators produce the
positive, normal-chain sign only), and compare two canonicalised sets as sets.

usage: wp2d_canon.py canon --k K --inp FILE --out OUT.npy        FILE: .npy (uint64) or text, one integer per line
       wp2d_canon.py compare --a A.npy --b B.npy
"""
import sys, argparse, itertools, time
import numpy as np


def load(path):
    if path.endswith('.npy'):
        return np.load(path).astype(np.uint64)
    vals = [int(line.split()[0]) for line in open(path) if line.strip() and not line.startswith('#')]
    return np.array(vals, dtype=np.uint64)


def perm_index(k, perm):
    """A2[a] = row read by the image g(x) = f(x_{perm[0]}, ..., x_{perm[k-1]}) at row a"""
    return np.array([sum((((a >> perm[j]) & 1) << j) for j in range(k)) for a in range(1 << k)], dtype=np.intp)


def canon(V, k):
    R = 1 << k
    assert R <= 64
    n = len(V)
    bits = ((V[:, None] >> np.arange(R, dtype=np.uint64)) & np.uint64(1)).astype(np.uint8)     # (n, R)
    cmin = V.copy()
    pad = np.zeros((n, 64 - R), dtype=np.uint8) if R < 64 else None
    for perm in itertools.permutations(range(k)):
        g = bits[:, perm_index(k, perm)]
        if pad is not None:
            g = np.concatenate([g, pad], axis=1)
        packed = np.ascontiguousarray(np.packbits(g, axis=1, bitorder='little')).view(np.uint64).reshape(n)
        np.minimum(cmin, packed, out=cmin)
    return np.unique(cmin)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['canon', 'compare'])
    ap.add_argument('--k', type=int); ap.add_argument('--inp'); ap.add_argument('--out')
    ap.add_argument('--a'); ap.add_argument('--b')
    a = ap.parse_args()
    t0 = time.time()
    if a.cmd == 'canon':
        V = np.unique(load(a.inp))
        C = canon(V, a.k)
        np.save(a.out, C)
        print(f'{a.inp}: {len(V)} distinct tables -> {len(C)} canonical classes under input permutation ({time.time() - t0:.1f} s)')
        return 0
    A, B = np.load(a.a), np.load(a.b)
    ab, ba = np.setdiff1d(A, B), np.setdiff1d(B, A)
    print(f'|A|={len(A)} |B|={len(B)} |A-B|={len(ab)} |B-A|={len(ba)} equal={len(ab) == 0 and len(ba) == 0} ({time.time() - t0:.1f} s)')
    if len(ab):
        print('A-B examples', ab[:5].tolist())
    if len(ba):
        print('B-A examples', ba[:5].tolist())
    return 0 if len(ab) == 0 and len(ba) == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
