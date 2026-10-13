"""WP3.2 metric reader: one row per result file in wp3/logs/wp32[...]/, the
pre-registered gradings P1-P8, and the exact LP over the certified types.

Usage (from wp3/): python -m gesat.summary [LOGDIR ...] [--out FILE.json]
"""
import glob
import json
import os
import statistics
import sys

from gecheck import lp
from .batch import LEAVES, INTERNAL, CONTROLS

P1 = ['1a', '1b', '2', '4', '5.1']
P4 = ['1a', '1b', '2', '3', '4', '5.1', '5.2.1', '5.2.2', '5.3', '5.4.1.1.1', '5.4.1.1.2', '5.4.1.2', '5.4.1.3',
      '5.4.1.4', '5.4.2.1', '5.4.2.2']
P4X = ['5.4.1.1.0']
P5 = ['5', '5.2', '5.4', '5.4.1', '5.4.1.1', '5.4.2']


def load(d):
    out = {}
    for f in sorted(glob.glob(os.path.join(d, '*.json'))):
        r = json.load(open(f))
        out[r['id']] = r
    return out


def row(r):
    fbs = sorted(set(p.get('FB') for p in r.get('partitions', []) if p.get('FB') is not None))
    return {'id': r['id'], 'status': r['status'], 'solve_s': r['solve_s'], 'encode_s': r['encode_s'],
            'n_vars': r['n_vars'], 'n_clauses': r['n_clauses'], 'partitions': len(r.get('partitions', [])),
            'FB': fbs, 'claimed_types': r.get('claimed_types'), 'certified_types': r.get('certified_types'),
            'drat_status': r.get('drat_status'), 'replay': r.get('replay_verdict'),
            'reason': r.get('reason')}


def report(d):
    R = load(d)
    rows = [row(r) for r in R.values()]
    print('== %s: %d result files' % (d, len(rows)))
    for x in sorted(rows, key=lambda x: x['id']):
        print('%-30s %-20s solve %7.1f s  encode %5.1f s  vars %8d  clauses %9d  parts %2d  FB %-14s %s %s' % (
            x['id'], x['status'], x['solve_s'], x['encode_s'], x['n_vars'], x['n_clauses'], x['partitions'],
            x['FB'], x['replay'] or '', (x['reason'] or '')[:60]))
    g = {}
    g['P1'] = {i: R[i]['status'] for i in P1 if i in R}
    g['P4'] = {i: R[i]['status'] for i in P4 if i in R}
    g['P4_unlabelled'] = {i: R[i]['status'] for i in P4X if i in R}
    g['P5'] = {i: R[i]['status'] for i in P5 if i in R}
    ctl = {}
    for m, _ in CONTROLS:
        if m in R:
            ctl[m] = (R[m]['status'], R[m].get('replay_verdict') or R[m].get('reason'))
    g['P2_P3_controls'] = ctl
    times = [r['solve_s'] for r in R.values() if r['status'] != 'REJECTED-STRUCTURAL']
    if times:
        g['P6'] = {'max_solve_s': max(times), 'median_solve_s': statistics.median(times),
                   'n_ge_600': sum(1 for t in times if t >= 600), 'n_instances': len(times)}
    g['P8'] = sorted(set(str(r.get('drat_status')) for r in R.values() if r['status'] == 'UNSAT'))
    cert = set()
    for i in P4 + P4X:
        if i in R and R[i]['status'] == 'UNSAT':
            cert.update(R[i].get('certified_types') or [])
    # the Case 5 defaults (types 3, 4) are certified wherever they discharge a
    # completion of a certified Case 5 leaf; they are claimed by node 5
    if any(i.startswith('5') and i in R and R[i]['status'] == 'UNSAT' for i in P4):
        cert.update([3, 4])
    cert = sorted(cert)
    g['certified_types'] = cert
    if cert:
        best, arg, tight = lp.solve(cert)
        g['P7_LP'] = {'types': cert, 'optimum': str(best), 'aT': str(arg[0]), 'aQ': str(arg[1]),
                      'equals_259_86': str(best) == '259/86'}
    for k, v in g.items():
        print('%s: %s' % (k, json.dumps(v, default=str)))
    return rows, g


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else None
    if out in args:
        args.remove(out)
    res = {}
    for d in args or ['logs/wp32']:
        res[d] = report(d)
    if out:
        with open(out, 'w') as f:
            json.dump({d: {'rows': r, 'grading': g} for d, (r, g) in res.items()}, f, indent=1, default=str)
