import sys, time, random
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/claude/progetti/circuit-lower-bounds')
import stable_check as sc
from topo import topologies

def all_tts(k, s, ops=5):
    full = (1 << (1 << k)) - 1
    T = topologies(k, s)
    U = set()
    for pairs in T:
        vals = [sc.var_mask(k, i) for i in range(k)] + [0] * s
        def rec(g):
            if g == s:
                U.add(vals[k + s - 1]); return
            a, b = pairs[g]; A, B = vals[a], vals[b]
            nA, nB = ~A & full, ~B & full
            for v in (A & B, A & nB, nA & B, A | B, A ^ B)[:ops]:
                vals[k + g] = v
                rec(g + 1)
        rec(0)
    return T, U

if __name__ == '__main__':
    random.seed(1)
    k = 6
    t1 = sc.tests_for('stable1', 6)
    sample = [random.getrandbits(64) for _ in range(2000)]
    print('sanity: random k=6 stable1 positives via repo predicate:', sum(sc._holds(t, t1) for t in sample), '/ 2000', flush=True)
    for (k, s) in [(3,2),(3,3),(4,3),(4,4),(5,4),(5,5),(6,5),(6,6)]:
        t0 = time.time()
        T, U = all_tts(k, s)
        ts, tw = sc.tests_for('stable1', k), sc.tests_for('weak1', k)
        st = [t for t in U if sc._holds(t, ts)]
        wk = [t for t in U if sc._holds(t, tw)]
        ness = sum(1 for t in U if len(sc.essential_vars(t, k)) != k)
        print(f'(k={k},s={s}) topologies={len(T)} distinct_tts={len(U)} not-all-essential={ness} '
              f'stable1={len(st)} weak1={len(wk)} {time.time()-t0:.1f}s', flush=True)
        if st: print('  STABLE1 WITNESSES', st[:5])
        if (k, s) == (5, 4):
            open('/tmp/advrev/weak1_54.txt', 'w').write('\n'.join(map(str, wk)))
