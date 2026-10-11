"""Reads results_targets.csv + frozen table and prints the pre-registered metric readings."""
import csv, json, collections
from simulate import check
from funcs import build
T = list(csv.DictReader(open('targets_frozen_2026-10-11.csv')))
R = collections.defaultdict(dict)
rows = list(csv.DictReader(open('results_targets.csv')))
for r in rows:
    R[r['f']][int(r['s'])] = r
ok = 0; lines = []
for t in T:
    f, e = t['f'], int(t['expected_s']); d = R.get(f, {})
    below = [d[s]['res'] if s in d else 'MISSING' for s in range(e)]
    at = d[e]['res'] if e in d else 'MISSING'
    sim = d[e]['sim'] if e in d else ''
    good = all(b == 'UNSAT' for b in below) and at == 'SAT' and sim == 'pass'
    ok += good
    tmax = max((float(x['wall_s']) for x in d.values()), default=0)
    um1 = d[e - 1]['wall_s'] if e - 1 in d else ''
    lines.append(f"{f:10s} n={t['n']} exp={e:2d} all_below_UNSAT={all(b=='UNSAT' for b in below)!s:5s} s-1={below[-1] if below else '-':8s}({um1}s) s={at:8s}({d[e]['wall_s'] if e in d else ''}s) sim={sim:4s} max_wall={tmax:8.1f} verified={t['verified']:14s} {'OK' if good else 'NOT-OK'}")
print('\n'.join(lines))
print(f'(a) rows with UNSAT(all s<exp) & SAT(exp) & sim pass: {ok}/{len(T)}')
by = collections.Counter((t['verified'], 'OK' if all(R.get(t['f'], {}).get(s, {}).get('res') == 'UNSAT' for s in range(int(t['expected_s']))) and R.get(t['f'], {}).get(int(t['expected_s']), {}).get('sim') == 'pass' else 'NOT-OK') for t in T)
print('    by source flag:', dict(by))
sat = [r for r in rows if r['res'] == 'SAT']
print(f"(c) SAT circuits: {len(sat)}  sim pass: {sum(r['sim']=='pass' for r in sat)}  sim FAIL: {sum(r['sim']=='FAIL' for r in sat)}")
# re-simulate from the stored circuit JSON in a fresh process + mutation control (complement output gate)
re_ok = mut_rej = mut_tot = 0
for r in sat:
    c = json.loads(r['circuit']); n, outs = build(r['f'])
    re_ok += check(c, outs)
    o = c['outputs'][0]
    if o >= n:
        g = c['gates'][o - n]; c['gates'][o - n] = (g[0], g[1], tuple(b ^ 1 for b in g[2]))
        mut_tot += 1; mut_rej += not check(c, outs)
print(f'    re-simulated from CSV: {re_ok}/{len(sat)} pass; control (output gate complemented) rejected: {mut_rej}/{mut_tot}')
to = [r for r in rows if r['res'] not in ('SAT', 'UNSAT')]
print(f'(d) TIMEOUT/ERROR rows: {len(to)}', [(r['f'], r['s'], r['res'], r['wall_s']) for r in to])
small = [r for r in rows if r['n'] != '5']; n5 = [r for r in rows if r['n'] == '5']
print(f"    P5 n!=5: {len(small)} instances, max wall {max(float(r['wall_s']) for r in small):.2f}s, over 60 s: {sum(float(r['wall_s'])>60 for r in small)}")
if n5: print(f"    P5 n=5 : {len(n5)} instances, max wall {max(float(r['wall_s']) for r in n5):.1f}s, over 7200 s or TIMEOUT: {sum(float(r['wall_s'])>7200 or r['res']=='TIMEOUT' for r in n5)}")
