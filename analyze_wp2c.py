"""WP2c metric reading: per-instance declarations (the brief's rule) and a line-by-line grading of P1-P5
against results_wp2c.csv.  usage: analyze_wp2c.py [--in results_wp2c.csv] [--sat-log log_wp2c_sat.txt]
A TIMEOUT or a missing row is "open", never UNSAT.  A SAT row counts as verified only if the SAT log has a
VERIFIED verdict for its (k, s, mode, tt).
"""
import argparse, csv, os, re

OPEN = [(6, 5), (6, 6), (7, 6)]
SANITY = [(6, s) for s in range(5)] + [(7, s) for s in range(6)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', default='results_wp2c.csv'); ap.add_argument('--sat-log', default='log_wp2c_sat.txt')
    a = ap.parse_args()
    rows = {}
    for r in csv.DictReader(open(a.inp)):
        if r['variant'] != 'stable1' or r['essential'] != '0':
            continue
        key = (int(r['k']), int(r['s']), r['mode'])
        rows[key] = r      # last row wins if an instance was run twice
    verified = set()
    if os.path.exists(a.sat_log):
        cur = None
        for line in open(a.sat_log):
            m = re.match(r'row stable1 k=(\d+) s=(\d+) mode=(\w+) tt=(\d+)', line)
            if m:
                cur = (int(m[1]), int(m[2]), m[3], m[4])
            if 'verdict: VERIFIED' in line and cur:
                verified.add(cur)

    def res(k, s, mode):
        r = rows.get((k, s, mode))
        return r['res'] if r else 'NOT_RUN'

    def wall(k, s, mode):
        r = rows.get((k, s, mode))
        return float(r['wall_s']) if r and r['wall_s'] else None

    print('== rows ==')
    for key in sorted(rows, key=lambda x: (x[0], x[2], x[1])):
        r = rows[key]
        print(f"k={key[0]} s={key[1]} mode={key[2]:4s} res={r['res']:7s} wall_s={float(r['wall_s']):8.1f} timeout_s={float(r['timeout_s']):.0f} sim={r['sim']} checker={r['checker']}")
    print('\n== per-instance declaration (brief rule) ==')
    decl = {}
    for k, s in OPEN:
        f, n = res(k, s, 'full'), res(k, s, 'none')
        if f == 'UNSAT' and n == 'UNSAT':
            d = 'UNSAT (both modes)'
        elif (f == 'SAT' and n == 'UNSAT') or (f == 'UNSAT' and n == 'SAT'):
            d = 'ENCODER DEFECT (modes disagree), no declaration'
        elif f == 'SAT' or n == 'SAT':
            vs = [m for m in ('full', 'none') if res(k, s, m) == 'SAT' and (k, s, m, rows[(k, s, m)]['tt']) in verified]
            d = f'SAT verified in mode(s) {vs}' if vs else 'SAT row(s) NOT verified -> open'
        else:
            d = f'open (full={f}, none={n})'
        decl[(k, s)] = d
        print(f'({k},{s}): {d}')
    allunsat = all(decl[x].startswith('UNSAT') for x in OPEN)
    print('global claim "7 is the minimum gadget size for this framework" (requires all three open instances UNSAT in both modes):', 'MADE' if allunsat else 'NOT MADE')

    print('\n== P1 ==')
    sats = [k for k, r in rows.items() if r['res'] == 'SAT']
    unsat_rows = sum(1 for r in rows.values() if r['res'] == 'UNSAT')
    print(f'SAT rows: {len(sats)} {sorted(sats)}; UNSAT rows: {unsat_rows}; TIMEOUT rows: {sum(1 for r in rows.values() if r["res"] == "TIMEOUT")}; rows present: {len(rows)} of 28')
    print('P1 (every completed row UNSAT, no SAT row):', 'HOLDS' if not sats else 'REFUTED')

    print('\n== P2 (six open rows complete UNSAT within 3600 s) ==')
    ok = True
    for k, s in OPEN:
        for m in ('full', 'none'):
            r = res(k, s, m); w = wall(k, s, m)
            print(f'({k},{s}) {m}: {r} wall_s={w}')
            ok = ok and r == 'UNSAT'
    print('P2 all six complete UNSAT:', 'HOLDS' if ok else 'REFUTED')

    print('\n== P3 (sanity rows) ==')
    ok18 = True
    for k, s in SANITY:
        if s > 4:
            continue
        for m in ('full', 'none'):
            r = res(k, s, m); w = wall(k, s, m)
            good = r == 'UNSAT' and w is not None and w < 300
            ok18 = ok18 and good
            if not good:
                print(f'  violates: ({k},{s}) {m}: {r} wall_s={w}')
    print('P3 18 rows s<=4 UNSAT in < 300 s:', 'HOLDS' if ok18 else 'REFUTED')
    ok75 = all(res(7, 5, m) == 'UNSAT' for m in ('full', 'none'))
    print('P3 (7,5) UNSAT within 3600 s in both modes:', 'HOLDS' if ok75 else 'REFUTED', {m: res(7, 5, m) for m in ('full', 'none')})

    print('\n== P4 (ordering) ==')
    mono = True
    for k in (6, 7):
        for m in ('full', 'none'):
            ws = [(s, wall(k, s, m)) for s in range(0, 7) if wall(k, s, m) is not None]
            for (s1, w1), (s2, w2) in zip(ws, ws[1:]):
                if w2 < w1:
                    mono = False; print(f'  wall decreases: k={k} {m} s={s1}->{s2}: {w1} -> {w2}')
    print('P4a wall_s non-decreasing in s within (k, mode):', 'HOLDS' if mono else 'REFUTED')
    tree = True
    for k in (6, 7):
        for m in ('full', 'none'):
            w1, w2 = wall(k, k - 2, m), wall(k, k - 1, m)
            r1, r2 = res(k, k - 2, m), res(k, k - 1, m)
            if w1 is None or w2 is None:
                print(f'  k={k} {m}: s={k-1} or s={k-2} not run -> undecided'); tree = None if tree else tree; continue
            if r1 == 'TIMEOUT':
                print(f'  k={k} {m}: s={k-2} TIMEOUT -> ratio undecidable'); tree = None if tree else tree; continue
            ratio = w2 / w1 if w1 > 0 else float('inf')
            note = '(lower bound, s=%d TIMEOUT)' % (k - 1) if r2 == 'TIMEOUT' else ''
            print(f'  k={k} {m}: wall(s={k-1})/wall(s={k-2}) = {w2:.1f}/{w1:.1f} = {ratio:.1f} {note}')
            if ratio < 10:
                tree = False
    print('P4b s=k-1 at least 10x slower than s=k-2:', {True: 'HOLDS', False: 'REFUTED', None: 'UNDECIDED'}[tree])
    nf = True
    for k in (6, 7):
        for s in range(4, 7):
            if res(k, s, 'full') == 'UNSAT' and wall(k, s, 'none') is not None:
                wf, wn = wall(k, s, 'full'), wall(k, s, 'none')
                print(f'  k={k} s={s}: full {wf:.1f} ({res(k, s, "full")}) vs none {wn:.1f} ({res(k, s, "none")})')
                if wn < wf:
                    nf = False
    print('P4c mode none >= mode full on UNSAT rows s>=4:', 'HOLDS' if nf else 'REFUTED')

    print('\n== P5 (hypothetical SAT) ==')
    if not sats:
        print('no SAT row: P5 not exercised')
    else:
        for key in sats:
            r = rows[key]
            print(key, 'verified' if (key[0], key[1], key[2], r['tt']) in verified else 'NOT verified', 'other mode:', res(key[0], key[1], 'none' if key[2] == 'full' else 'full'))


if __name__ == '__main__':
    main()
