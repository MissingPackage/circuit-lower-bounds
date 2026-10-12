import sys, itertools
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/claude/progetti/circuit-lower-bounds')
import stable_check as sc
from topo import topologies
def transform(tt, perm, neg, oneg, k=5):
    r = 0
    for t in range(1 << k):
        x = [(t >> i) & 1 for i in range(k)]
        z = sum((x[perm[i]] ^ ((neg >> i) & 1)) << i for i in range(k))
        r |= (((tt >> z) & 1) ^ oneg) << t
    return r
# C3b: are the 32 chain positives in the NPN orbit of the WP2b argmin?
chain = ((0,1),(2,5),(0,3),(4,7),(6,8),(1,3),(9,10)); full = (1<<32)-1
U=set(); vals=[sc.var_mask(5,i) for i in range(5)]+[0]*7
def rec(g):
    if g==7: U.add(vals[11]); return
    a,b=chain[g]; A,B=vals[a],vals[b]; nA,nB=~A&full,~B&full
    for v in (A&B,A&nB,nA&B,A|B,A^B): vals[5+g]=v; rec(g+1)
rec(0); ts=sc.tests_for('stable1',5); pos=[t for t in U if sc._holds(t,ts)]
orbit=set(transform(3939033088,p,n,o) for p in itertools.permutations(range(5)) for n in range(32) for o in (0,1))
print('C3b orbit size', len(orbit), '(WP2b says 768); chain positives in argmin orbit:', sum(t in orbit for t in pos), '/', len(pos), flush=True)

# C4: the reconstructed s=k proof step, checked per structure with an independent domination test
def check_structure(k, pairs):
    n = k + len(pairs); out = n - 1
    succ = {v: [] for v in range(n)}; kids = {}
    for i, (a, b) in enumerate(pairs):
        g = k + i; kids[g] = (a, b); succ[a].append(g); succ[b].append(g)
    def reaches_out_avoiding(v, G):
        st, seen = [v], set()
        while st:
            x = st.pop()
            if x == out: return True
            for z in succ[x]:
                if z != G and z not in seen: seen.add(z); st.append(z)
        return False
    def cone_inputs(v):
        st, seen = [v], set()
        while st:
            x = st.pop()
            if x in seen: continue
            seen.add(x)
            if x >= k: st.extend(kids[x])
        return [x for x in seen if x < k]
    # pairs (x, y): x input of fan-out 1 feeding G=op(u,x), y in cone(u), x and y both dominated by G
    good = []
    for x in range(k):
        if len(succ[x]) != 1: continue
        G = succ[x][0]; u = kids[G][0] if kids[G][1] == x else kids[G][1]
        for y in cone_inputs(u):
            if y != x and not reaches_out_avoiding(y, G) and not reaches_out_avoiding(x, G):
                good.append((x, y, G)); break
    return good
_cache = {}
def test_fails(tt, k, x, y):
    key = (k, x, y)
    if key not in _cache:
        rest = [v for v in range(k) if v not in (x, y)]; alts = []
        for tau in itertools.product((0,1), repeat=len(rest)):
            M = sc.rows_mask(k, dict(zip(rest, tau))); xy = sc.var_mask(k, y) & M
            alts.append((M, xy)); alts.append((M, M & ~xy))
        _cache[key] = alts
    return not any((tt & M) == P for M, P in _cache[key])
def run(k):
    T = topologies(k, k); full = (1 << (1 << k)) - 1
    nogood = 0; viol = 0; checked = 0
    for pairs in T:
        good = check_structure(k, pairs)
        if not good: nogood += 1; continue
        x, y, G = good[0]
        vals = [sc.var_mask(k, i) for i in range(k)] + [0]*k
        def rec(g):
            nonlocal viol, checked
            if g == k:
                checked += 1
                if not test_fails(vals[-1], k, x, y): viol += 1
                return
            a, b = pairs[g]; A, B = vals[a], vals[b]; nA, nB = ~A & full, ~B & full
            for v in (A&B, A&nB, nA&B, A|B, A^B): vals[k+g] = v; rec(g+1)
        if k <= 6: rec(0)
    print(f'C4 k={k}: structures={len(T)} without a dominated (x,y) pair={nogood}; (Y={{x,y}},y) test fails on {checked-viol}/{checked} op assignments ', flush=True)

for k in (4, 5, 6): run(k)
