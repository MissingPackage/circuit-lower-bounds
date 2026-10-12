"""WP2d stage B (R3 mechanical): the stability verdicts of stable_check.py are invariant under NPN
transformations (input permutation, input negation, output negation) at k = 6 and k = 7.
Generalisation of npn_invariance.py (WP2b, k = 5): own transform code, the oracle is stable_check
(the checker's test lists are built once per variant with stable_check.tests_for and applied with
stable_check._holds, which is what stable_check.holds does per call; at k = 7 rebuilding the lists
on every call would dominate the run time).

Pool per k: positives found by uniform random sampling of 2^k-bit tables until NEED positives are
found, plus 300 random NPN images of those positives, plus random tables up to PAIRS entries.
For every pool entry f a fresh random transform is drawn and the verdicts of f and of its image are
compared for stable1, weak1, stable2 and stable1pos.

usage: wp2d_npn_invariance.py [--pairs 2000] [--need 60] [--seed S] [--k 6 7]
exit status 0 iff, at every k, changes == 0 for stable1, weak1, stable2, positives(stable1) >= 50
and stable1pos has >= 1 change.
"""
import sys, argparse, random, time
import stable_check


def npn(tt, k, perm, neg, out):
    """g(x) = f(x_{perm[0]} ^ neg_0, ..., x_{perm[k-1]} ^ neg_{k-1}) ^ out, WP1 integers"""
    R = 1 << k
    g = 0
    for a in range(R):
        a2 = sum(((((a >> perm[j]) & 1) ^ ((neg >> j) & 1)) << j) for j in range(k))
        g |= ((tt >> a2) & 1) << a
    return g ^ ((1 << R) - 1 if out else 0)


def random_transform(rnd, k):
    return list(rnd.sample(range(k), k)), rnd.getrandbits(k), rnd.randrange(2)


def run_k(k, pairs, need, rnd):
    R = 1 << k
    tests = {v: stable_check.tests_for(v, k) for v in ('stable1', 'weak1', 'stable2', 'stable1pos')}
    t0 = time.time()
    # positives by random sampling
    positives, sampled = [], 0
    while len(positives) < need:
        f = rnd.getrandbits(R)
        sampled += 1
        if stable_check._holds(f, tests['stable1']):
            positives.append(f)
    print(f'k={k}: {len(positives)} stable1 positives found in {sampled} random tables ({time.time() - t0:.1f} s)', flush=True)
    pool = list(positives)
    for _ in range(300):
        pool.append(npn(rnd.choice(positives), k, *random_transform(rnd, k)))
    while len(pool) < pairs:
        pool.append(rnd.getrandbits(R))
    ok = True
    for variant in ('stable1', 'weak1', 'stable2', 'stable1pos'):
        pos = changes = 0
        examples = []
        for f in pool:
            perm, neg, out = random_transform(rnd, k)
            g = npn(f, k, perm, neg, out)
            vf, vg = stable_check._holds(f, tests[variant]), stable_check._holds(g, tests[variant])
            pos += vf
            if vf != vg:
                changes += 1
                if len(examples) < 2:
                    examples.append((f, perm, neg, out, vf, vg))
        print(f'k={k} {variant}: pairs={len(pool)} positives={pos} changes={changes} examples={examples}', flush=True)
        if variant == 'stable1pos':
            ok &= changes >= 1
        else:
            ok &= changes == 0
            if variant == 'stable1':
                ok &= pos >= 50
    # every positive must be weak1 (GHKK: m-stable implies weakly m-stable) and depend on every input (A1)
    w = sum(stable_check._holds(f, tests['weak1']) for f in positives)
    e = sum(len(stable_check.essential_vars(f, k)) == k for f in positives)
    print(f'k={k}: of {len(positives)} stable1 positives, weak1={w}, all-inputs-essential={e}', flush=True)
    ok &= w == len(positives) == e
    print(f'k={k}: elapsed_s={time.time() - t0:.1f}', flush=True)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pairs', type=int, default=2000)
    ap.add_argument('--need', type=int, default=60)
    ap.add_argument('--seed', type=int, default=20261012)
    ap.add_argument('--k', type=int, nargs='+', default=[6, 7])
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    ok = True
    for k in a.k:
        ok &= run_k(k, a.pairs, a.need, rnd)
    print(f'result={"PASS" if ok else "FAIL"}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
