"""Reads results_wp2_*.csv (+ log_wp2_counts.txt) and prints the pre-registered WP2 metric readings.
Every SAT row is re-simulated from the stored circuit JSON (simulate.check, WP1) and re-checked by the
independent checker (stable_check, own simulation) in this process.  Minima: exact only with UNSAT at every
s' < s (mode full, non-monotone with U) or UNSAT at s-1 (mode none); TIMEOUT never counts as UNSAT."""
import csv, glob, json, collections
from simulate import check
import stable_check

rows = []
for fn in sorted(glob.glob('results_wp2_*.csv')):
    if fn.endswith('_min.csv'):
        continue
    for r in csv.DictReader(open(fn)):
        r['file'] = fn; rows.append(r)
G = collections.defaultdict(dict)
for r in rows:
    G[(r['variant'], int(r['k']), r['mode'], r['essential'])][int(r['s'])] = r

print('=== per-instance ladders (variant k mode ess): s -> res [wall/timeout] ===')
status = {}
for key in sorted(G):
    d = G[key]
    parts = []
    for s in sorted(d):
        r = d[s]; tag = r['res']
        if tag == 'SAT':
            tag += '(sim=%s,chk=%s,tt=%s)' % (r['sim'], r['checker'], r['tt'])
        parts.append('%d:%s[%.0f/%s]' % (s, tag, float(r['wall_s']), r['timeout_s'].split('.')[0]))
    sats = [s for s in sorted(d) if d[s]['res'] == 'SAT' and d[s]['checker'] == 'accept' and d[s]['sim'] == 'pass']
    unsat = [s for s in sorted(d) if d[s]['res'] == 'UNSAT']
    other = [(s, d[s]['res']) for s in sorted(d) if d[s]['res'] not in ('SAT', 'UNSAT')]
    if sats:
        m = min(sats)
        if key[2] == 'full':
            exact = all(s in d and d[s]['res'] == 'UNSAT' for s in range(m))
        else:
            exact = (m - 1) in d and d[m - 1]['res'] == 'UNSAT' or m == 0
        st = f'min_s={m} EXACT' if exact else f'upper_bound={m}, UNSAT at {unsat}, undecided {other}'
    else:
        st = f'no certified SAT; UNSAT at {unsat}; undecided {other}'
    status[key] = st
    print(' '.join(map(str, key)), '::', ' '.join(parts))
    print('      ->', st)

print('\n=== P3: re-simulation and independent re-check of every SAT row ===')
sat = [r for r in rows if r['res'] == 'SAT']
re_sim = re_chk = rej = 0
for r in sat:
    c = json.loads(r['circuit']); k = int(r['k'])
    prop = 'stable1' if r['variant'] == 'fixed_gst1' else r['variant']
    tt = stable_check.circuit_tt(c)
    ok_chk = stable_check.holds(tt, k, prop, r['essential'] == '1')
    tts = [[(tt >> t) & 1 for t in range(1 << k)]]
    ok_sim = check(c, tts) and (r['variant'] != 'fixed_gst1' or tt == 376339136)
    re_sim += ok_sim; re_chk += ok_chk; rej += (r['checker'] != 'accept')
print(f'SAT rows: {len(sat)}; sim pass (re-run): {re_sim}; checker accept (re-run): {re_chk}; '
      f'checker reject recorded in CSV: {rej}; gates <= 10 and accepted: '
      f'{[(r["variant"], r["k"], r["s"], r["tt"]) for r in sat if int(r["s"]) <= 10 and r["checker"] == "accept" and r["variant"] in ("stable1", "stable1pos", "stable2")]}')

print('\n=== exhaustive counts (log_wp2_counts.txt) ===')
try:
    print(open('log_wp2_counts.txt').read().strip())
except FileNotFoundError:
    print('missing')

print('\n=== TIMEOUT / ERROR / SKIPPED rows ===')
for r in rows:
    if r['res'] not in ('SAT', 'UNSAT'):
        print(r['variant'], r['k'], r['s'], r['mode'], r['essential'], r['res'], r['wall_s'], r['timeout_s'])
