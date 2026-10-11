"""WP2c stage B: controls C1-C5 of wp2c_preregistration_2026-10-11.txt, run before any WP2c instance.
Writes log_wp2c_controls.txt (stdout copy) and results_wp2c_smoke.csv (C5 solver rows).
Exit status 0 iff every expected verdict holds.
"""
import csv, json, random, sys, time
import stable_check
from encoder import Enc
import stability
from funcs import build

OK = True
out = open('log_wp2c_controls.txt', 'w')


def log(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True); out.write(s + '\n'); out.flush()


def expect(cond, what):
    global OK
    log(('PASS' if cond else 'FAIL'), what)
    OK = OK and cond


def pad(tt, k_from):
    return tt | (tt << (1 << k_from))


log('WP2c controls', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))

# C1: x1x2x3 + x4x5x6 at k = 6
tt_c1 = 9187484529235886208
r = stable_check.report(tt_c1, 6)
log('C1', json.dumps(r))
expect(r['weak1'] is True and r['stable1'] is False and r['essential'] == [0, 1, 2, 3, 4, 5], 'C1 x1x2x3+x4x5x6: weak1 accept, stable1 reject')
expect(stable_check.holds(tt_c1, 6, 'weak1') and not stable_check.holds(tt_c1, 6, 'stable1'), 'C1 holds() agrees with report()')

# C2: padded gst1 / argmin / WP2 function at k = 6 and k = 7
for name, tt5 in [('gst1', 376339136), ('argmin_0x00071357', 3939033088), ('wp2_found', 9178798)]:
    r5 = stable_check.report(tt5, 5)
    tt6 = pad(tt5, 5); r6 = stable_check.report(tt6, 6)
    tt7 = pad(tt6, 6); r7 = stable_check.report(tt7, 7)
    log('C2', name, 'k=5', json.dumps(r5))
    log('C2', name, 'k=6', json.dumps(r6))
    log('C2', name, 'k=7', json.dumps(r7))
    expect(r5['stable1'] is True and r5['essential'] == [0, 1, 2, 3, 4], f'C2 {name} unpadded stable1 accept at k=5')
    expect(r6['stable1'] is False and r6['essential'] == [0, 1, 2, 3, 4], f'C2 {name} padded (dummy x6) stable1 reject at k=6, essential = five inputs')
    expect(r7['stable1'] is False and r7['essential'] == [0, 1, 2, 3, 4], f'C2 {name} padded (dummy x6, x7) stable1 reject at k=7')
    # the padded function is still weakly 1-stable? Not necessarily required; recorded only.
    # the specific failing clause: Y = {x6}, no tau gives +-x6
    tests = stable_check._stable_tests(6, 1, 'both')
    failing = [i for i, alts in enumerate(tests) if not any((tt6 & M) == P for M, P in alts)]
    log('C2', name, 'k=6 failing (Y,y) test indices:', failing[:10], 'count', len(failing))

# C3: random positive at k = 6
rng = random.Random(20261011)
found = None
t0 = time.time()
for i in range(100000):
    tt = rng.getrandbits(64)
    if stable_check.holds(tt, 6, 'stable1'):
        found = (i + 1, tt); break
expect(found is not None, 'C3 random 1-stable 6-input function found')
if found:
    n_tried, tt = found
    r = stable_check.report(tt, 6)
    log('C3 found after', n_tried, 'samples in %.1fs' % (time.time() - t0), json.dumps(r))
    expect(r['stable1'] is True and r['weak1'] is True and r['essential'] == [0, 1, 2, 3, 4, 5], 'C3 positive: stable1 accept, weak1 accept, all six inputs essential')
    # how frequent: count among the first 2000 samples
    rng2 = random.Random(1); c = sum(stable_check.holds(rng2.getrandbits(64), 6, 'stable1') for _ in range(2000))
    log('C3 frequency estimate: %d / 2000 random 64-bit tables are stable1' % c)

# C4: encoder build at k = 6, 7 (free path both modes, fixed path on padded tables)
for k in (6, 7):
    for mode in ('full', 'none'):
        for s in range(0, 7):
            e = Enc(k, 1, s, mode=mode, sym=False)
            aux = stability.add_variant(e, 'stable1', essential_inputs=False)
            log('C4 free', 'k=%d' % k, 'mode=%s' % mode, 's=%d' % s, 'rows=%d' % e.R, 'vars=%d' % e.nv, 'clauses=%d' % len(e.cl), 'aux=%d' % aux)
            expect(e.R == 1 << k and len(e.fv) == 1 << k, f'C4 free k={k} mode={mode} s={s}: {1 << k} rows / fv variables')
    tt5 = 376339136
    tt = pad(tt5, 5) if k == 6 else pad(pad(tt5, 5), 6)
    n, outs = build(f'TT_{k}_{tt}')
    e = Enc(n, outs, 3, mode='full', sym=False)
    log('C4 fixed', f'TT_{k}_{tt}', 'n=%d' % n, 'rows=%d' % len(outs[0]), 'vars=%d' % e.nv, 'clauses=%d' % len(e.cl))
    expect(n == k and len(outs[0]) == 1 << k and sum(b << t for t, b in enumerate(outs[0])) == tt, f'C4 fixed path TT_{k}_ builds with {1 << k} rows and round-trips')

# C5: end-to-end smoke solves (rows to results_wp2c_smoke.csv)
from solve_wp2 import run as run_free
from solve import run as run_fixed
FIELDS = ['variant', 'k', 's', 'mode', 'essential', 'res', 'wall_s', 'timeout_s', 'solve_s', 'vars', 'clauses', 'aux_vars', 'sim', 'checker', 'tt', 'circuit']
fh = open('results_wp2c_smoke.csv', 'w', newline=''); w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader()
for mode in ('full', 'none'):
    r = run_free('weak1', 6, 3, mode=mode, essential=False, timeout=600)
    w.writerow({f: r.get(f, '') for f in FIELDS}); fh.flush()
    log('C5 weak1 k=6 s=3', mode, r['res'], r['sim'], r['checker'], 'tt=%s' % r['tt'], '%.1fs' % r['wall_s'])
    expect(r['res'] == 'SAT' and r['sim'] == 'pass' and r['checker'] == 'accept', f'C5 weak1 k=6 s=3 mode={mode}: SAT, sim pass, checker accept')
for name, s, want in [('AND_6', 4, 'UNSAT'), ('AND_6', 5, 'SAT'), ('AND_7', 5, 'UNSAT'), ('AND_7', 6, 'SAT')]:
    r = run_fixed(name, s, mode='full', sym='auto', timeout=600)
    row = dict(variant='fixed_' + name, k=r['n'], s=s, mode='full', essential='', res=r['res'], wall_s=r['wall_s'], timeout_s=r['timeout_s'],
               solve_s=r['solve_s'], vars=r['vars'], clauses=r['clauses'], aux_vars=0, sim=r['sim'], checker='', tt='', circuit=r['circuit'])
    w.writerow(row); fh.flush()
    log('C5 fixed', name, 's=%d' % s, r['res'], r['sim'], '%.1fs' % r['wall_s'])
    expect(r['res'] == want and (want == 'UNSAT' or r['sim'] == 'pass'), f'C5 fixed {name} s={s}: expected {want}')
fh.close()
log('ALL CONTROLS', 'PASS' if OK else 'FAIL')
out.close()
sys.exit(0 if OK else 1)
