"""WP2b driver: decode Knuth's table (optimal5/knuthies.dat), validate it, cross-check the cost convention
against WP1/WP2 values, and read off the minimum cost over 1-stable / weakly 1-stable / 2-stable classes.
Single-threaded; no SAT solving unless a stable1 class of cost <= 10 appears (then one WP1-encoder run,
< 60 s).  Outputs (all in the repository root):
  results_wp2b_classes.csv        one row per NPN class (616,126)
  results_wp2b_knuth_hist.csv     class / function histogram per cost vs checktab.py
  results_wp2b_crosscheck.csv     convention cross-check (targets, bfs3, sym4, gst1, WP2 SAT function)
  results_wp2b_stability_hist.csv cost histogram (classes, functions) per stability variant
  results_wp2b_argmin.csv         argmin classes with decoded circuits and their verification
"""
import csv, json, sys, time, random
from collections import Counter
import optimal5_glue as g
import stable_check
from simulate import check as sim_check
from funcs import build

K, R, M32 = 5, 32, 0xffffffff
GROUP = 7680
KNUTH_CLASSES = [2, 2, 5, 20, 93, 389, 1988, 11382, 60713, 221541, 293455, 26535, 1]
KNUTH_FUNCS = [12, 100, 1140, 11570, 109826, 995240, 8430800, 63401728, 383877392, 1519125536, 2123645248, 195366784, 1920]
GST1 = 376339136
WP2_SAT = 9178798
T0 = time.time()


def log(*a):
    print('%7.1fs' % (time.time() - T0), *a, flush=True)


def pad_to_5(tt, n):
    """WP1 integer of an n-input function as a 5-input function (x_{n+1}.. dummy)"""
    m = (1 << n) - 1
    return sum(((tt >> (t & m)) & 1) << t for t in range(R))


def find_transform(src, dst):
    """(perm, neg, out) with transform_wp1(src, ...) == dst, or None"""
    for (perm, neg), s in g.SIGMA.items():
        img = sum(((src >> s[a]) & 1) << a for a in range(R))
        if img == dst:
            return list(perm), neg, 0
        if img ^ M32 == dst:
            return list(perm), neg, 1
    return None


def main():
    # ------------------------------------------------------------------ A. decode
    recs = g.load_records()
    keys = [g.chain_tt_opt5(r) for r in recs]
    assert len(set(keys)) == g.N_RECORDS and all(k < (1 << 31) for k in keys)
    recs = recs + [[], []]
    keys = keys + [0x00000000, 0x0000ffff]          # the two trivial classes implicit in optimal5.h load_chains()
    N = len(keys)
    assert N == 616126
    index = {k: i for i, k in enumerate(keys)}
    ngates = [len(r) for r in recs]
    ch = Counter(ngates)
    class_hist = [ch[c] for c in range(13)]
    log('decoded', N, 'classes; class histogram', class_hist, 'matches Knuth:', class_hist == KNUTH_CLASSES)

    # ------------------------------------------------------------------ B. orbit sizes + orbit-minimum check (packed, 64-bit slots)
    pk = g.Packed(N, 64)
    Q = g.pack(keys, 64)
    GUARD = g.rep_mask(1 << 32, N, 64)
    stab = 0
    less = 0
    nt = 0
    for P in pk.walk(Q):
        e1 = pk.equal(P, Q)
        e2 = pk.equal(P ^ pk.W, Q)
        stab += e1 + e2
        ge = (((Q | GUARD) - P) >> 32) & pk.ONE          # 1 iff Q >= P (slot-wise)
        less |= ge & (e1 ^ pk.ONE)                       # 1 iff P < Q strictly
        nt += 1
        if nt % 640 == 0:
            log('orbit pass', nt, '/ 3840')
    assert nt == 3840
    raw = stab.to_bytes(N * 8, 'little')
    stabs = [int.from_bytes(raw[8 * i:8 * i + 8], 'little') for i in range(N)]
    assert all(GROUP % s == 0 for s in stabs)
    orbit = [GROUP // s for s in stabs]
    n_less = sum(g.unpack_lsb(less, N, 64))
    fh = [0] * 13
    for c, o in zip(ngates, orbit):
        fh[c] += o
    log('orbit sum', sum(orbit), '== 2^32:', sum(orbit) == 1 << 32, '| keys that are NOT their orbit minimum:', n_less)
    log('function histogram', fh, 'matches Knuth:', fh == KNUTH_FUNCS)
    with open('results_wp2b_knuth_hist.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['cost', 'classes', 'classes_knuth', 'classes_match', 'functions', 'functions_knuth', 'functions_match'])
        for c in range(13):
            w.writerow([c, class_hist[c], KNUTH_CLASSES[c], int(class_hist[c] == KNUTH_CLASSES[c]), fh[c], KNUTH_FUNCS[c], int(fh[c] == KNUTH_FUNCS[c])])
        w.writerow(['sum', sum(class_hist), sum(KNUTH_CLASSES), int(sum(class_hist) == sum(KNUTH_CLASSES)), sum(fh), 1 << 32, int(sum(fh) == 1 << 32)])
    # the trivial classes must have the known orbits
    assert orbit[index[0]] == 2 and orbit[index[0x0000ffff]] == 10

    # ------------------------------------------------------------------ C. stability verdicts (packed, WP1 convention, 32-bit slots)
    tts = [g.opt5_to_wp1(k) for k in keys]
    pk32 = g.Packed(N, 32)
    V = g.pack(tts, 32)
    ONE = pk32.ONE
    verdict = {}
    for variant in ('stable1', 'weak1', 'stable2'):
        allok = ONE
        for alts in stable_check.tests_for(variant, K):
            req = 0
            for M, P in alts:
                z = (V & g.rep_mask(M, N, 32)) ^ g.rep_mask(P, N, 32)
                req |= g.nonzero_slots(z) & ONE ^ ONE
            allok &= req
        verdict[variant] = g.unpack_lsb(allok, N, 32)
        log(variant, 'accepted classes', sum(verdict[variant]))
    ess = 0
    for i in range(K):
        z = ((V & pk32.SET[i]) >> (1 << i)) ^ (V & pk32.CLR[i])
        ess += g.nonzero_slots(z) & ONE
    essential = [b & 7 for b in ess.to_bytes(N * 4, 'little')[0::4]]
    # validation of the packed evaluation against stable_check.holds / essential_vars on a sample + every accepted class
    rnd = random.Random(20261011)
    sample = set(rnd.sample(range(N), 20000))
    for variant in verdict:
        sample |= {i for i in range(N) if verdict[variant][i]}
    sample |= {index[k] for k in (g.wp1_to_opt5(0), 0x0000ffff)}
    mism = Counter()
    tests = {v: stable_check.tests_for(v, K) for v in verdict}     # built once (holds() rebuilds them per call)
    for i in sample:
        for variant in verdict:
            if bool(verdict[variant][i]) != stable_check._holds(tts[i], tests[variant]):
                mism[variant] += 1
        if essential[i] != len(stable_check.essential_vars(tts[i], K)):
            mism['essential'] += 1
    log('packed-vs-stable_check validation on', len(sample), 'classes: mismatches', dict(mism))
    assert not mism
    incl = dict(stable2_not_stable1=sum(1 for i in range(N) if verdict['stable2'][i] and not verdict['stable1'][i]),
                stable1_not_weak1=sum(1 for i in range(N) if verdict['stable1'][i] and not verdict['weak1'][i]))
    log('inclusion violations', incl)
    with open('results_wp2b_classes.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['tt_opt5', 'tt_wp1', 'n_gates', 'orbit', 'stable1', 'weak1', 'stable2', 'essential'])
        for i in range(N):
            w.writerow(['%08x' % keys[i], tts[i], ngates[i], orbit[i], verdict['stable1'][i], verdict['weak1'][i], verdict['stable2'][i], essential[i]])
    log('wrote results_wp2b_classes.csv')

    # ------------------------------------------------------------------ D. convention cross-check
    def lookup(tt5):
        orb = g.orbit_opt5(tt5)
        hits = [index[w] for w in orb if w in index]
        assert len(hits) == 1, ('orbit must contain exactly one representative', len(hits))
        return hits[0]

    rows = []

    def add(name, n, tt_n, ours, source, upper_bound=False):
        tt5 = pad_to_5(tt_n, n)
        i = lookup(tt5)
        knuth = ngates[i]
        deg = knuth == 0 and ours == 1
        if upper_bound and knuth < ours:
            deg = False
            source += ' [our value is an UPPER BOUND only: SAT at that s, no UNSAT ladder below]'
        sim = ''
        if knuth >= 1:
            tr = find_transform(tts[i], tt5)
            circ = g.transform_circuit(g.chain_to_wp1_circuit(recs[i]), *tr)
            bits = [(tt5 >> t) & 1 for t in range(R)]
            sim = 'pass' if (sim_check(circ, [bits]) and stable_check.circuit_tt(circ) == tt5 and len(circ['gates']) == knuth) else 'FAIL'
        note = 'degenerate: constant or negated literal costs 1 gate in WP1, 0 in Knuth' if deg else ('' if ours == knuth else (
            'upper bound only; table value below it is not a contradiction (see log_wp2b_sat.txt for the SAT ladder)' if upper_bound and knuth < ours else 'UNEXPLAINED'))
        rows.append(dict(name=name, n=n, tt_wp1=tt_n, ours=ours, source=source, optimal5=knuth, rep='%08x' % keys[i],
                         match=int(ours == knuth), degenerate=int(deg), sim=sim, note=note))

    for r in csv.DictReader(open('targets_frozen_2026-10-11.csv')):
        n, outs = build(r['f'])
        if len(outs) != 1 or n > 5:
            continue
        add(r['f'], n, sum(b << t for t, b in enumerate(outs[0])), int(r['expected_s']), 'WP1 ' + r['verified'])
    add('gst1 TT_5_%d' % GST1, 5, GST1, 11, 'GHKK Lemma 4 (fixed ladder UNSAT through s=7 so far)')
    add('WP2 stable1 SAT TT_5_%d' % WP2_SAT, 5, WP2_SAT, 11, 'WP2 SAT at s=11 (single-s job; free-function ladder s<=8 still running)', upper_bound=True)
    for r in csv.DictReader(open('results_bfs3.csv')):
        add('bfs3 tt=%s' % r['tt'], 3, int(r['tt']), int(r['bfs_min']), 'results_bfs3.csv')
    seen = set()
    for r in csv.DictReader(open('results_sym4_min.csv')):
        if r['f'] in seen or r['status'] != 'SAT':
            continue
        seen.add(r['f'])
        add('sym4 ' + r['f'], 4, int(r['f'].split('_')[2]), int(r['min_s']), 'results_sym4_min.csv ' + r['stage'])
    with open('results_wp2b_crosscheck.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    unexpl = [r['name'] for r in rows if not r['match'] and not r['degenerate']]
    degs = [r['name'] for r in rows if r['degenerate']]
    sims = Counter(r['sim'] for r in rows)
    log('cross-check rows', len(rows), '| unexplained mismatches', len(unexpl), unexpl, '| degenerate mismatches', len(degs), degs, '| sim', dict(sims))
    for r in rows:
        if r['source'].startswith('WP1 yes-glyphcount') or 'gst1' in r['name'] or 'WP2' in r['name']:
            log('  ', r['name'], 'ours', r['ours'], 'optimal5', r['optimal5'], 'sim', r['sim'])

    # ------------------------------------------------------------------ E. stability results
    hist_rows, arg_rows = [], []
    gst1_rep = keys[lookup(GST1)]
    wp2_rep = keys[lookup(WP2_SAT)]
    log('gst1 class', '%08x' % gst1_rep, 'cost', ngates[index[gst1_rep]], '| WP2 SAT function class', '%08x' % wp2_rep, 'cost', ngates[index[wp2_rep]])
    for variant, essflag in (('stable1', 0), ('weak1', 0), ('weak1', 1), ('stable2', 0)):
        acc = [i for i in range(N) if verdict[variant][i] and (not essflag or essential[i] == K)]
        hc, hf = Counter(), Counter()
        for i in acc:
            hc[ngates[i]] += 1
            hf[ngates[i]] += orbit[i]
        for c in range(13):
            hist_rows.append([variant, essflag, c, hc[c], hf[c]])
        mn = min((ngates[i] for i in acc), default='')
        log(variant, 'essential=%d' % essflag, 'classes', len(acc), 'functions', sum(orbit[i] for i in acc), 'min cost', mn,
            'hist', [hc[c] for c in range(13)])
        if mn == '':
            arg_rows.append(dict(variant=variant, essential_required=essflag, min_cost='', tt_opt5='', tt_wp1='', orbit='', essential='',
                                 chain='', circuit_wp1='', sim='', checker='', is_gst1_class='', is_wp2_sat_class=''))
            continue
        for i in acc:
            if ngates[i] != mn:
                continue
            circ = g.chain_to_wp1_circuit(recs[i])
            bits = [(tts[i] >> t) & 1 for t in range(R)]
            sim = 'pass' if (sim_check(circ, [bits]) and stable_check.circuit_tt(circ) == tts[i]) else 'FAIL'
            chk = 'accept' if stable_check.holds(tts[i], K, variant, bool(essflag)) else 'reject'
            arg_rows.append(dict(variant=variant, essential_required=essflag, min_cost=mn, tt_opt5='%08x' % keys[i], tt_wp1=tts[i],
                                 orbit=orbit[i], essential=essential[i], chain=g.chain_text(recs[i]), circuit_wp1=json.dumps(circ),
                                 sim=sim, checker=chk, is_gst1_class=int(keys[i] == gst1_rep), is_wp2_sat_class=int(keys[i] == wp2_rep)))
    with open('results_wp2b_stability_hist.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['variant', 'essential_required', 'cost', 'n_classes', 'n_functions'])
        w.writerows(hist_rows)
    with open('results_wp2b_argmin.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(arg_rows[0].keys()))
        w.writeheader()
        w.writerows(arg_rows)
    s1 = [r for r in arg_rows if r['variant'] == 'stable1' and r['min_cost'] != '']
    log('stable1 argmin classes', len(s1), 'sim', Counter(r['sim'] for r in s1), 'checker', Counter(r['checker'] for r in s1),
        'gst1 among argmin', any(r['is_gst1_class'] for r in s1), 'WP2 SAT function among argmin', any(r['is_wp2_sat_class'] for r in s1))
    if s1 and s1[0]['min_cost'] <= 10:
        log('stable1 minimum <= 10: running the WP1-encoder SAT check at s = min (timeout 60 s) on the first argmin class')
        from solve import run
        r = run('TT_5_%d' % s1[0]['tt_wp1'], s1[0]['min_cost'], mode='full', sym=False, timeout=60)
        log('SAT check', {k: r[k] for k in ('res', 'sim', 'wall_s')})
    log('done')


if __name__ == '__main__':
    sys.exit(main())
