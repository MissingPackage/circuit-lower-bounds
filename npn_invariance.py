"""WP2b step 1: mechanical test that the stability verdicts of stable_check.py are invariant under NPN
transformations (input permutation, input negation, output negation).  Own transform code (5 lines), the
oracle is stable_check.holds.

Argument (Definition 2, both signs; Definition 1): an input permutation relabels Y, y and tau; an input
negation with mask N is absorbed by replacing tau with tau xor N on X \\ Y, and if y in N the restricted
function changes from y to not y (both signs are admitted by Definition 2; Definition 1 has no sign);
an output negation swaps the two signs (Definition 2) or swaps tau_0 and tau_1 (Definition 1).  So
stable1, stable2 and weak1 are class properties.  The positive-sign-only variant stable1pos is NOT
invariant under output negation nor under negation of the variable y.

usage: npn_invariance.py [--pairs N] [--seed S]   -> one line per variant: pairs, positives, changes
exit status 0 iff changes == 0 for stable1, weak1, stable2 and changes >= 1 for stable1pos.
"""
import sys, argparse, random, time
import stable_check

K, R = 5, 32
GST1 = 376339136      # GHKK Lemma 4, WP1 integer
WP2_SAT = 9178798     # WP2 SAT-found 1-stable function (results_wp2_k5.csv, s=11)
M32 = 0xffffffff


def npn(tt, perm, neg, out):
    """g(x) = f(x_{perm[0]} ^ neg_0, ..., x_{perm[4]} ^ neg_4) ^ out, WP1 integers"""
    g = 0
    for a in range(R):
        a2 = sum(((((a >> perm[j]) & 1) ^ ((neg >> j) & 1)) << j) for j in range(K))
        g |= ((tt >> a2) & 1) << a
    return g ^ (M32 if out else 0)


def random_transform(rnd):
    return list(rnd.sample(range(K), K)), rnd.getrandbits(K), rnd.randrange(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pairs', type=int, default=2400)
    ap.add_argument('--seed', type=int, default=20261011)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    # function pool: the two known 1-stable functions, 300 random NPN images of them, and random functions
    pool = [GST1, WP2_SAT]
    for _ in range(300):
        pool.append(npn(rnd.choice((GST1, WP2_SAT)), *random_transform(rnd)))
    while len(pool) < a.pairs:
        pool.append(rnd.getrandbits(R))
    t0 = time.time()
    ok = True
    for variant in ('stable1', 'weak1', 'stable2', 'stable1pos'):
        pos = changes = 0
        examples = []
        for f in pool:
            perm, neg, out = random_transform(rnd)
            g = npn(f, perm, neg, out)
            vf, vg = stable_check.holds(f, K, variant), stable_check.holds(g, K, variant)
            pos += vf
            if vf != vg:
                changes += 1
                if len(examples) < 3:
                    examples.append((f, perm, neg, out, vf, vg))
        print(f'{variant}: pairs={len(pool)} positives={pos} changes={changes} examples={examples}')
        ok &= (changes == 0) if variant != 'stable1pos' else (changes >= 1)
    # the named stable1pos case: NOT gst1
    ng = GST1 ^ M32
    r = dict(gst1_stable1pos=stable_check.holds(GST1, K, 'stable1pos'), not_gst1_stable1pos=stable_check.holds(ng, K, 'stable1pos'),
             not_gst1_stable1=stable_check.holds(ng, K, 'stable1'))
    print('named case', r)
    ok &= r['gst1_stable1pos'] and not r['not_gst1_stable1pos'] and r['not_gst1_stable1']
    print(f'elapsed_s={time.time() - t0:.1f} result={"PASS" if ok else "FAIL"}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
