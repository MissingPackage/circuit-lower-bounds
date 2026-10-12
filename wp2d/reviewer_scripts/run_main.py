import sys, time, random
sys.dont_write_bytecode = True
from evalc import *
random.seed(1)
# 1) vectorised predicate vs repo checker on random 6-input tables (incl. positives)
k = 6
sample = [random.getrandbits(64) for _ in range(3000)]
v = stable_vec(np.array(sample, dtype=np.uint64), k, 'stable1')
ref = [sc.is_m_stable(t, k, 1) for t in sample]
print('predicate agreement k=6 stable1:', sum(int(a) == int(b) for a, b in zip(v, ref)), '/', len(sample), 'positives', sum(ref))
for (k, s) in [(3,2),(3,3),(4,3),(4,4),(5,4),(5,5),(6,5),(6,6)]:
    t0 = time.time()
    T, U = all_tts(k, s)
    ess_ok = sum(1 for t in U[:2000] if len(sc.essential_vars(int(t), k)) == k)
    st = stable_vec(U, k, 'stable1')
    wk = stable_vec(U, k, 'weak1')
    print(f'(k={k},s={s}) topologies={len(T)} distinct_tts={len(U)} all-essential(first2000)={ess_ok}/{min(2000,len(U))} '
          f'stable1={int(st.sum())} weak1={int(wk.sum())} {time.time()-t0:.1f}s', flush=True)
    if k == 5 and s == 4:
        np.save('/tmp/advrev/weak1_54.npy', U[wk])
