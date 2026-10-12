"""WP2d: exhaustive enumeration of circuit structures (own enumerator, written before reading
wp2d/reviewer_scripts/).  See wp2d_preregistration_2026-10-12.txt for R1-R3 and the design.

E(k, s) = truth tables (WP1 integers: bit t = f on row t, x_{i+1} = (t >> i) & 1) of all circuits with
k inputs, s gates, gate types in N = {AND, OR, XOR, a AND NOT b, NOT a AND b}, both argument nodes
distinct, every node in the output cone (all inputs used), inputs labelled by first use, gates in a
canonical topological order (adjacent independent gates in non-decreasing (a, b) order).

Two evaluators over the same structure generator:
  enum_dfs(k, s)   pure-Python bit-parallel depth-first search (reference)
  enum_vec(k, s)   numpy: all 5^s type assignments of one structure at once

subcommands:
  selftest                  structure counts, dfs == vec on small instances, witnesses re-simulate
  main --k K --s S          one main-run instance: distinct count, stable1 count via stable_check.holds
  control3                  k = 3 cost comparison with results_bfs3.csv
  control5                  k = 5 class-level completeness control against Knuth's table (WP2b)
"""
import sys, os, time, json, csv, argparse, itertools
import numpy as np
import stable_check

OPS = ('AND', 'OR', 'XOR', 'ANDNOT', 'NOTAND')
OP_TABLE = {0: [0, 0, 0, 1], 1: [0, 1, 1, 1], 2: [0, 1, 1, 0], 3: [0, 0, 1, 0], 4: [0, 1, 0, 0]}   # [f00, f01, f10, f11]
T0 = time.time()


def log(*a):
    print('%8.1fs' % (time.time() - T0), *a, flush=True)


def var_mask(k, i):
    return sum(1 << t for t in range(1 << k) if (t >> i) & 1)


def E0(k):
    """s = 0 by convention: constants and projections"""
    return {0, (1 << (1 << k)) - 1} | {var_mask(k, i) for i in range(k)}


# ---------------------------------------------------------------- structures
def candidates(k, n, u):
    """pairs (a, b), a < b, among nodes 0..n-1 allowed by the first-use rule when inputs 0..u-1 are used"""
    avail = list(range(u)) + list(range(k, n))
    c = [(avail[x], avail[y]) for x in range(len(avail)) for y in range(x + 1, len(avail))]
    if u < k:
        c += [(a, u) for a in range(u)]
        c += [(u, b) for b in range(k, n)]
        if u + 1 < k:
            c.append((u, u + 1))
    return c


def structures(k, s):
    """yields lists of s pairs (a, b): every node in the output cone, first-use input labelling,
    adjacent independent gates in non-decreasing (a, b) order"""
    if s == 0 or k < 2:
        return
    outdeg = [0] * (k + s)
    pairs = [None] * s

    def rec(i, u, D):
        r = s - i - 1
        n = k + i
        prev = pairs[i - 1] if i else None
        for a, b in candidates(k, n, u):
            D2 = D - (outdeg[a] == 0) - (outdeg[b] == 0) + 1
            if D2 > r + 1 or (r == 0 and D2 != 1):
                continue
            if i and n - 1 not in (a, b) and (a, b) < prev:
                continue
            u2 = u + (a == u) + (b == u) + (a == u and b == u + 1)
            outdeg[a] += 1; outdeg[b] += 1
            pairs[i] = (a, b)
            if r == 0:
                yield list(pairs)
            else:
                yield from rec(i + 1, u2, D2)
            outdeg[a] -= 1; outdeg[b] -= 1

    yield from rec(0, 0, k)


def count_structures(k, s):
    return sum(1 for _ in structures(k, s))


# ---------------------------------------------------------------- pure-Python evaluator
def enum_dfs(k, s, collect=None):
    """set of distinct truth tables of E(k, s); returns (set, structures, leaves)"""
    if s == 0:
        return (E0(k), 0, 0)
    X = [var_mask(k, i) for i in range(k)]
    found = set() if collect is None else collect
    nstruct = nleaves = 0
    for pairs in structures(k, s):
        nstruct += 1
        nleaves += 5 ** s
        vals = X + [0] * s
        def rec(i):
            a, b = pairs[i]
            A, B = vals[a], vals[b]
            cands = (A & B, A | B, A ^ B, A & ~B, ~A & B)
            if i == s - 1:
                found.update(cands)
            else:
                j = k + i
                for c in cands:
                    vals[j] = c
                    rec(i + 1)
        rec(0)
    return found, nstruct, nleaves


def find_witness(k, s, target):
    """(pairs, ops) of a circuit in E(k, s) computing target, or None"""
    X = [var_mask(k, i) for i in range(k)]
    for pairs in structures(k, s):
        vals = X + [0] * s
        ops = [0] * s

        def rec(i):
            a, b = pairs[i]
            A, B = vals[a], vals[b]
            cands = (A & B, A | B, A ^ B, A & ~B, ~A & B)
            for o, c in enumerate(cands):
                ops[i] = o
                if i == s - 1:
                    if c == target:
                        return True
                else:
                    vals[k + i] = c
                    if rec(i + 1):
                        return True
            return False
        if rec(0):
            return pairs, list(ops)
    return None


def to_wp1_circuit(k, pairs, ops):
    return dict(n=k, gates=[[a, b, list(OP_TABLE[o])] for (a, b), o in zip(pairs, ops)], outputs=[k + len(pairs) - 1])


def circuit_text(k, pairs, ops):
    def name(v):
        return 'x%d' % (v + 1) if v < k else 'g%d' % (v - k + 1)
    return '; '.join('g%d = %s(%s, %s)' % (i + 1, OPS[o], name(a), name(b)) for i, ((a, b), o) in enumerate(zip(pairs, ops)))


# ---------------------------------------------------------------- numpy evaluator
_OPIDX = {}


def opidx(s):
    if s not in _OPIDX:
        idx = np.arange(5 ** s)
        _OPIDX[s] = [((idx // 5 ** i) % 5).astype(np.intp) for i in range(s)]
    return _OPIDX[s]


def words_of(k):
    return max(1, (1 << k) // 64)


def split_words(v, nw):
    """Python int -> tuple of nw np.uint64 words (little-endian 64-bit chunks)"""
    return tuple(np.uint64((v >> (64 * w)) & 0xffffffffffffffff) for w in range(nw))


def join_words(ws):
    return sum(int(w) << (64 * i) for i, w in enumerate(ws))


def eval_vec(k, s, pairs, X):
    """all 5^s type assignments of one structure; returns list of nw arrays (uint64) of length 5^s"""
    nw = len(X[0])
    oi = opidx(s)
    vals = list(X)
    for i, (a, b) in enumerate(pairs):
        A, B = vals[a], vals[b]
        out = []
        for w in range(nw):
            Aw, Bw = A[w], B[w]
            out.append(np.choose(oi[i], [Aw & Bw, Aw | Bw, Aw ^ Bw, Aw & ~Bw, ~Aw & Bw]))
        vals.append(tuple(out))
    return vals[-1]


def unique_rows(ws):
    """distinct values of a list of word arrays -> array of shape (M,) (nw == 1) or (M, nw), sorted"""
    if len(ws) == 1:
        return np.unique(ws[0])
    return np.unique(np.stack(ws, axis=1), axis=0)


def enum_vec(k, s, sink=None):
    """sink(unique_array) per structure (default: accumulate and merge); returns (merged or None, structures, leaves)"""
    if s == 0:
        arr = np.array(sorted(E0(k)), dtype=object)
        return arr, 0, 0
    nw = words_of(k)
    X = [split_words(var_mask(k, i), nw) for i in range(k)]
    acc = []
    nstruct = nleaves = 0
    for pairs in structures(k, s):
        nstruct += 1
        nleaves += 5 ** s
        u = unique_rows(eval_vec(k, s, pairs, X))
        if sink is None:
            acc.append(u)
        else:
            sink(u)
    if sink is not None:
        return None, nstruct, nleaves
    if not acc:
        return np.zeros((0,) if nw == 1 else (0, nw), dtype=np.uint64), nstruct, nleaves
    cat = np.concatenate(acc)
    return (np.unique(cat) if nw == 1 else np.unique(cat, axis=0)), nstruct, nleaves


def arr_to_ints(arr):
    if arr.ndim == 1:
        return [int(v) for v in arr]
    return [join_words(row) for row in arr]


def ints_to_arr(vals, k):
    nw = words_of(k)
    if nw == 1:
        return np.unique(np.array(sorted(vals), dtype=np.uint64))
    rows = np.array([[(v >> (64 * w)) & 0xffffffffffffffff for w in range(nw)] for v in sorted(vals)], dtype=np.uint64)
    return np.unique(rows, axis=0)


# ---------------------------------------------------------------- vectorised stable1 check (k <= 6, one word)
def stable1_vec(vals, k, tests=None):
    """boolean array: stable_check's stable1 tests applied to a uint64 array (same masks/patterns)"""
    tests = tests or stable_check.tests_for('stable1', k)
    ok = np.ones(len(vals), dtype=bool)
    for alts in tests:
        acc = np.zeros(len(vals), dtype=bool)
        for M, P in alts:
            acc |= (vals & np.uint64(M)) == np.uint64(P)
        ok &= acc
        if not ok.any():
            break
    return ok


# ---------------------------------------------------------------- subcommands
def cmd_selftest(a):
    import wp2d_struct_count
    ok = True
    log('structure counts (enumerator vs wp2d_struct_count.py)')
    for k, s in [(2, 1), (3, 2), (3, 3), (3, 4), (4, 3), (4, 4), (4, 5), (5, 4), (5, 5), (6, 5), (6, 6), (7, 6)]:
        c1, c2 = count_structures(k, s), wp2d_struct_count.count(k, s)
        log(f'  ({k},{s}) {c1} {c2} {"ok" if c1 == c2 else "MISMATCH"}')
        ok &= c1 == c2
    # (2,1): exactly the five normal non-degenerate functions of two inputs
    e, _, _ = enum_dfs(2, 1)
    x1, x2 = var_mask(2, 0), var_mask(2, 1)
    want = {x1 & x2, x1 | x2, x1 ^ x2, x1 & ~x2, ~x1 & x2}
    log(f'  E(2,1) = {sorted(e)} expected {sorted(want)} {"ok" if e == want else "MISMATCH"}')
    ok &= e == want
    # every node in the cone: check on all structures of a few instances
    for k, s in [(4, 4), (5, 5), (6, 6), (7, 6)]:
        bad = 0
        for pairs in structures(k, s):
            od = [0] * (k + s)
            for a_, b_ in pairs:
                od[a_] += 1; od[b_] += 1
            if any(od[v] == 0 for v in range(k + s - 1)) or od[k + s - 1] != 0:
                bad += 1
        log(f'  ({k},{s}) structures with a node outside the cone: {bad}')
        ok &= bad == 0
    # dfs == vec on small instances, witnesses re-simulate (stable_check.circuit_tt and simulate.check)
    from simulate import check as sim_check
    for k, s in [(3, 2), (3, 3), (3, 4), (4, 3), (4, 4), (4, 5), (5, 4), (5, 5), (6, 5), (7, 6)]:
        d, ns, nl = enum_dfs(k, s)
        v, ns2, nl2 = enum_vec(k, s)
        same = np.array_equal(ints_to_arr(d, k), v) and ns == ns2 and nl == nl2
        log(f'  ({k},{s}) dfs distinct={len(d)} vec distinct={len(v)} structures={ns} leaves={nl} {"same" if same else "DIFFERENT"}')
        ok &= same
        import random
        rnd = random.Random(k * 100 + s)
        for tt in rnd.sample(sorted(d), min(5, len(d))):
            w = find_witness(k, s, tt)
            circ = to_wp1_circuit(k, *w)
            tt_bits = [(tt >> t) & 1 for t in range(1 << k)]
            good = stable_check.circuit_tt(circ) == tt and sim_check(circ, [tt_bits])
            ok &= good
            if not good:
                log('  WITNESS FAILURE', k, s, tt, w)
    log('selftest', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


def save_set(k, s, arr, tag):
    os.makedirs('wp2d', exist_ok=True)
    path = f'wp2d/E_{k}_{s}{tag}.npy'
    np.save(path, arr)
    return path


def cmd_main(a):
    k, s = a.k, a.s
    rows = []
    for ev in (['dfs', 'vec'] if a.evaluator == 'both' else [a.evaluator]):
        t0 = time.time()
        if ev == 'dfs':
            d, ns, nl = enum_dfs(k, s)
            arr = ints_to_arr(d, k)
            vals = sorted(d)
        else:
            arr, ns, nl = enum_vec(k, s)
            vals = arr_to_ints(arr)
        t_enum = time.time() - t0
        path = save_set(k, s, arr, '' if ev == 'dfs' else '_vec')
        log(f'({k},{s}) {ev}: structures={ns} leaves={nl} distinct={len(vals)} enum_s={t_enum:.1f} saved {path}')
        # stable1 on every distinct truth table with the checker (tests built once; holds() rebuilds them per call)
        tests = stable_check.tests_for('stable1', k)
        t1 = time.time()
        hits = [v for v in vals if stable_check._holds(v, tests)]
        t_chk = time.time() - t1
        ess_all = sum(1 for v in vals if len(stable_check.essential_vars(v, k)) == k) if a.essential_count else -1
        log(f'({k},{s}) {ev}: stable1 hits={len(hits)} check_s={t_chk:.1f} all-inputs-essential={ess_all}')
        vec_hits = -1
        if words_of(k) == 1:
            vec_hits = int(stable1_vec(arr, k, tests).sum())
            log(f'({k},{s}) {ev}: vectorised stable1 hits={vec_hits} (cross-check)')
        for h in hits:
            w = find_witness(k, s, h)
            circ = to_wp1_circuit(k, *w)
            r = stable_check.report(h, k)
            log('HIT', json.dumps(dict(k=k, s=s, tt=h, circuit=circ, text=circuit_text(k, *w), sim_tt=stable_check.circuit_tt(circ) == h, report=r)))
        rows.append(dict(k=k, s=s, evaluator=ev, structures=ns, leaves=nl, distinct=len(vals), stable1=len(hits),
                         stable1_vec=vec_hits, all_inputs_essential=ess_all, enum_s=round(t_enum, 1), check_s=round(t_chk, 1),
                         hits=' '.join(str(h) for h in hits[:20]), status='exhaustive', set_file=path))
    out = a.out
    new = not os.path.exists(out)
    with open(out, 'a', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if new:
            w.writeheader()
        for r in rows:
            w.writerow(r)
    return 0


def permute_tt(tt, k, perm):
    """g(x) = f(x_{perm[0]}, ..., x_{perm[k-1]})"""
    g = 0
    for a in range(1 << k):
        a2 = sum((((a >> perm[j]) & 1) << j) for j in range(k))
        g |= ((tt >> a2) & 1) << a
    return g


def pad(tt, j, k):
    """j-input function on the first j of k inputs"""
    m = (1 << j) - 1
    return sum(((tt >> (t & m)) & 1) << t for t in range(1 << k))


def expand(vals, k):
    """closure under input permutation and output negation"""
    full = (1 << (1 << k)) - 1
    out = set()
    for v in vals:
        for perm in itertools.permutations(range(k)):
            g = permute_tt(v, k, perm)
            out.add(g); out.add(g ^ full)
    return out


def union_unused(k, smax, evaluator='dfs'):
    """E(k, <= s, unused inputs allowed) for s = 0..smax: dict s -> set, via the padded union over j <= k;
    the per-(j, s) exact sets are returned too"""
    exact = {}
    for j in range(k + 1):
        for s in range(smax + 1):
            if s == 0:
                ex = E0(j) if j else {0, 1}
            elif j < 2 or j > s + 1:
                ex = set()
            else:
                if evaluator == 'dfs':
                    ex, _, _ = enum_dfs(j, s)
                else:
                    arr, _, _ = enum_vec(j, s)
                    ex = set(arr_to_ints(arr))
            exact[j, s] = ex
    cum = {}
    run = set()
    for s in range(smax + 1):
        for j in range(k + 1):
            run |= {pad(v, j, k) for v in exact[j, s]}
        cum[s] = set(run)
    return cum, exact


def cmd_control3(a):
    smax = 4
    cum, exact = union_unused(3, smax)
    for s in range(smax + 1):
        log(f'k=3 s<={s}: |E(3,<=s, unused allowed)|={len(cum[s])} expanded={len(expand(cum[s], 3))}')
    bfs = {int(r['tt']): int(r['bfs_min']) for r in csv.DictReader(open('results_bfs3.csv'))}
    cost = {}
    for s in range(smax + 1):
        for v in expand(cum[s], 3):
            cost.setdefault(v, s)
    rows = []
    mism = []
    for tt in range(256):
        c = cost.get(tt, -1)
        rows.append(dict(tt=tt, bfs_min=bfs[tt], enum_cost=c, match=int(c == bfs[tt])))
        if c != bfs[tt]:
            mism.append(tt)
    with open('results_wp2d_bfs3.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['tt', 'bfs_min', 'enum_cost', 'match'])
        w.writeheader(); w.writerows(rows)
    log(f'k=3: rows matching bfs_min = {256 - len(mism)} of 256; mismatches tt={mism} (bfs {[bfs[t] for t in mism]}, enum {[cost.get(t, -1) for t in mism]})')
    log(f'k=3: functions never produced: {sum(1 for t in range(256) if t not in cost)}')
    # also: are the exact-s sets for s = 5, 6 contained in E(3, <= 4)?  (every 3-input function has cost <= 4)
    for s in (5, 6):
        arr, ns, nl = enum_vec(3, s)
        ex = set(arr_to_ints(arr))
        extra = {v for v in ex if cost.get(v, -1) < 0}
        log(f'k=3 s={s}: structures={ns} distinct={len(ex)} not already covered by s<=4: {len(extra)}')
    return 0


# ---------------------------------------------------------------- k = 5 class-level control
POP8 = np.array([bin(i).count('1') for i in range(256)], dtype=np.uint8)


def popcount(bm):
    return int(sum(int(POP8[bm[i:i + (1 << 24)]].sum(dtype=np.int64)) for i in range(0, len(bm), 1 << 24)))


def bitmap_set(bm, vals):
    vals = np.unique(vals.astype(np.uint64))
    for b in range(8):
        sel = vals[(vals & np.uint64(7)) == np.uint64(b)]
        bm[(sel >> np.uint64(3)).astype(np.int64)] |= np.uint8(1 << b)


def bitmap_get(bm, vals):
    v = vals.astype(np.uint64)
    return ((bm[(v >> np.uint64(3)).astype(np.int64)] >> (v & np.uint64(7)).astype(np.uint8)) & 1).astype(bool)


def cmd_control5(a):
    import optimal5_glue as g
    K, R = 5, 32
    M32 = 0xffffffff
    smax = a.smax
    # orbit machinery (WP1 convention): SIG[m, a] = row read by image m at row a
    keys = list(g.SIGMA.keys())
    SIG = np.array([g.SIGMA[key] for key in keys], dtype=np.intp)          # (3840, 32)
    POW = (np.uint64(1) << np.arange(32, dtype=np.uint64))
    TOFB = np.array(g.T_OF_B, dtype=np.uint64)

    def orbit_wp1(tt):
        bits = np.array([(tt >> t) & 1 for t in range(R)], dtype=np.uint64)
        imgs = (bits[SIG] * POW).sum(axis=1).astype(np.uint64)
        return np.unique(np.concatenate([imgs, imgs ^ np.uint64(M32)]))

    def wp1_to_opt5_vec(v):
        v = v.astype(np.uint64)
        w = np.zeros(len(v), dtype=np.uint64)
        for b in range(R):
            w |= ((v >> TOFB[b]) & np.uint64(1)) << np.uint64(b)
        return w

    def canon_key(tt):
        """minimum over the NPN orbit in optimal5 convention (the key of results_wp2b_classes.csv)"""
        return int(wp1_to_opt5_vec(orbit_wp1(tt)).min())

    # self-check of the orbit code against optimal5_glue.orbit_opt5 on a few tables
    import random
    rnd = random.Random(5)
    for _ in range(5):
        tt = rnd.getrandbits(32)
        o1 = set(int(x) for x in wp1_to_opt5_vec(orbit_wp1(tt)))
        o2 = set(g.orbit_opt5(tt).keys())
        assert o1 == o2, 'orbit code mismatch'
    assert canon_key(3939033088) == 0x00071357
    log('orbit code agrees with optimal5_glue.orbit_opt5 on 5 random tables; canon_key(TT_5_3939033088) = 0x00071357')

    classes = []
    with open('results_wp2b_classes.csv') as f:
        for r in csv.DictReader(f):
            classes.append((int(r['tt_opt5'], 16), int(r['tt_wp1']), int(r['n_gates']), int(r['essential']), int(r['stable1'])))
    log('classes loaded', len(classes))
    exp_cum = [sum(1 for c in classes if c[2] <= s) for s in range(smax + 1)]
    exp_cum_ess = {e: [sum(1 for c in classes if c[2] <= s and c[3] == e) for s in range(smax + 1)] for e in range(6)}
    log('expected cumulative classes', exp_cum, 'by essential', exp_cum_ess)

    bm = np.zeros(1 << 29, dtype=np.uint8)        # 2^32 bits, cumulative E(5, <= s, unused allowed)
    tests5 = stable_check.tests_for('stable1', K)
    rows = []
    # which (j, s) to run: j = 5 all s; j = 4 all s; j = 3 up to 6; j = 2 up to 5 (beyond: every function already present, checked)
    run_limit = {5: smax, 4: smax, 3: min(smax, 6), 2: min(smax, 5), 1: 0, 0: 0}
    small_cover = {}
    for s in range(smax + 1):
        new_vals_small = set()
        per_j = {}
        for j in range(6):
            if s > run_limit[j]:
                per_j[j] = 'skipped'
                continue
            t0 = time.time()
            if j == 5:
                st = [0, 0]

                def sink(u, st=st):
                    st[0] += 1
                    bitmap_set(bm, u)
                _, ns, nl = enum_vec(5, s, sink)
                per_j[j] = f'structures={ns} leaves={nl}'
            else:
                if s == 0:
                    ex = E0(j) if j else {0, 1}
                    ns = nl = 0
                elif j < 2 or j > s + 1:
                    ex, ns, nl = set(), 0, 0
                else:
                    arr, ns, nl = enum_vec(j, s)
                    ex = set(arr_to_ints(arr))
                small_cover.setdefault(j, set()).update(ex)
                padded = np.array([pad(v, j, 5) for v in ex], dtype=np.uint64)
                if len(padded):
                    bitmap_set(bm, padded)
                per_j[j] = f'structures={ns} leaves={nl} distinct={len(ex)} cover_j={len(expand(small_cover[j], j)) if j else len(small_cover[j])}/{1 << (1 << j)}'
            log(f's={s} j={j}: {per_j[j]} ({time.time() - t0:.1f} s)')
        n_distinct = popcount(bm)
        # class scan
        t0 = time.time()
        hit_by_ess = {e: 0 for e in range(6)}
        covered = 0
        hit_classes = []
        for key, tt_wp1, cost, ess, st1 in classes:
            if cost > s:
                continue
            orb = orbit_wp1(tt_wp1)
            inb = bitmap_get(bm, orb)
            c = int(inb.sum())
            if c:
                hit_by_ess[ess] += 1
                covered += c
                hit_classes.append((key, cost, ess, st1, c, len(orb)))
        n_hit = sum(hit_by_ess.values())
        violations = n_distinct - covered
        log(f's<={s}: distinct(padded, cumulative)={n_distinct} classes_hit={n_hit} expected={exp_cum[s]} '
            f'by_essential={[hit_by_ess[e] for e in range(6)]} expected={[exp_cum_ess[e][s] for e in range(6)]} '
            f'covered_by_cost<={s}_orbits={covered} containment_violations={violations} ({time.time() - t0:.1f} s)')
        stable_hits = -1
        stable_classes = ''
        if s in a.stable_at:
            # chunked vectorised stable1 over every set bit of the bitmap, validated against stable_check on a sample + positives
            t0 = time.time()
            hits = []
            n_checked = 0
            sample_mism = 0
            sample_n = 0
            CH = 1 << 23
            for c0 in range(0, len(bm), CH):
                bits = np.unpackbits(bm[c0:c0 + CH], bitorder='little')
                vals = (np.nonzero(bits)[0].astype(np.uint64) + np.uint64(c0 * 8))
                if not len(vals):
                    continue
                n_checked += len(vals)
                ok = stable1_vec(vals, K, tests5)
                pos = vals[ok]
                hits.extend(int(v) for v in pos)
                # validation sample: 600 random per chunk + all positives
                idx = rnd.sample(range(len(vals)), min(600, len(vals)))
                for i in idx:
                    sample_n += 1
                    sample_mism += stable_check._holds(int(vals[i]), tests5) != bool(ok[i])
                for v in pos:
                    sample_n += 1
                    sample_mism += stable_check._holds(int(v), tests5) != True
            stable_hits = len(hits)
            ck = sorted(set(canon_key(h) for h in hits))
            stable_classes = ' '.join('%08x' % c for c in ck)
            log(f's<={s}: stable1 over {n_checked} produced tables: hits={stable_hits} classes={stable_classes} '
                f'validation sample={sample_n} mismatches={sample_mism} ({time.time() - t0:.1f} s)')
            if hits:
                hmin = min(hits)
                log(f's<={s}: example hit tt={hmin} report={stable_check.report(hmin, K)}')
            assert sample_mism == 0
        rows.append(dict(s=s, distinct_cumulative=n_distinct, classes_hit=n_hit, classes_expected=exp_cum[s], match=int(n_hit == exp_cum[s]),
                         hit_ess5=hit_by_ess[5], exp_ess5=exp_cum_ess[5][s], hit_ess4=hit_by_ess[4], exp_ess4=exp_cum_ess[4][s],
                         hit_ess3=hit_by_ess[3], exp_ess3=exp_cum_ess[3][s], hit_ess2=hit_by_ess[2], exp_ess2=exp_cum_ess[2][s],
                         hit_ess01=hit_by_ess[0] + hit_by_ess[1], exp_ess01=exp_cum_ess[0][s] + exp_cum_ess[1][s],
                         covered=covered, containment_violations=violations, stable1_hits=stable_hits, stable1_classes=stable_classes,
                         runs=' | '.join(f'j={j}: {per_j[j]}' for j in range(6)), status='exhaustive'))
        with open('results_wp2d_control5.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['selftest', 'main', 'control3', 'control5'])
    ap.add_argument('--k', type=int); ap.add_argument('--s', type=int)
    ap.add_argument('--evaluator', default='dfs', choices=['dfs', 'vec', 'both'])
    ap.add_argument('--out', default='results_wp2d_main.csv')
    ap.add_argument('--essential-count', action='store_true')
    ap.add_argument('--smax', type=int, default=7)
    ap.add_argument('--stable-at', type=int, nargs='*', default=[6, 7])
    a = ap.parse_args()
    return dict(selftest=cmd_selftest, main=cmd_main, control3=cmd_control3, control5=cmd_control5)[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
