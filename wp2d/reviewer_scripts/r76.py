import sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/claude/progetti/circuit-lower-bounds')
import stable_check as sc
from evalp import all_tts
for k, s in [(7, 6)]:
    t0 = time.time(); T, U = all_tts(k, s); ts = sc.tests_for('stable1', k)
    st = [t for t in U if sc._holds(t, ts)]
    print(f'(k={k},s={s}) topologies={len(T)} distinct_tts={len(U)} stable1={len(st)} {time.time()-t0:.1f}s', flush=True)
