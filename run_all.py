"""Single driver.  usage: run_all.py <stage> [options]
  targets   : frozen target table -> results_targets.csv (ladder s=0..expected, +2 if still UNSAT)
  p3        : all 256 functions of 3 variables, SAT min-s with mode none and mode full vs BFS
  sym4      : all 32 symmetric functions of 4 variables: full+S vs full without S (validates constraint S)
Every (f,s) instance = one child process with hard timeout; unfinished instances are recorded as TIMEOUT."""
import csv, sys, argparse, threading, time
from concurrent.futures import ThreadPoolExecutor
from solve import run

FIELDS = ['stage', 'f', 'n', 's', 'mode', 'sym', 'res', 'sim', 'wall_s', 'solve_s', 'vars', 'clauses', 'timeout_s', 'circuit']
lock = threading.Lock()

def ladder(stage, name, mode, sym, timeout, smax, w, fh, smin=0):
    """increase s until SAT / TIMEOUT / smax. returns (min_s or None, status)"""
    for s in range(smin, smax + 1):
        r = run(name, s, mode=mode, sym=sym, timeout=timeout)
        r['stage'] = stage
        with lock:
            w.writerow({k: r.get(k, '') for k in FIELDS}); fh.flush()
            print(time.strftime('%H:%M:%S'), stage, name, 's=%d' % s, mode, 'sym=%d' % r['sym'], r['res'], r['sim'], r['wall_s'], flush=True)
        if r['res'] == 'SAT':
            return s, 'SAT'
        if r['res'] != 'UNSAT':
            return None, r['res'] + '@%d' % s
    return None, 'UNSAT<=%d' % smax

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('stage'); ap.add_argument('--out'); ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--only', default=''); ap.add_argument('--t-small', type=float, default=1800)
    ap.add_argument('--t-n5', type=float, default=7200)
    a = ap.parse_args()
    out = a.out or f'results_{a.stage}.csv'
    fh = open(out, 'w', newline=''); w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader()
    jobs = []
    if a.stage == 'targets':
        rows = list(csv.DictReader(open('targets_frozen_2026-10-11.csv')))
        if a.only:
            rows = [r for r in rows if r['f'] in a.only.split(',')]
        for r in rows:
            n = int(r['n']); exp = int(r['expected_s'])
            # hard timeout: P5 budget is 60 s for n<=4 (and n=6 P1 rows) / 7200 s for n=5; small instances get a
            # longer hard limit so that a budget miss is still measured rather than hidden.
            to = a.t_n5 if n == 5 else a.t_small
            jobs.append(('targets', r['f'], 'full', 'auto', to, exp + 2))
    elif a.stage == 'p3':
        for v in range(256):
            jobs.append(('p3-none', f'TT_3_{v}', 'none', False, 600, 6))
            jobs.append(('p3-full', f'TT_3_{v}', 'full', 'auto', 600, 6))
    elif a.stage == 'sym4':
        for m in range(32):  # m = set of weights on which f is 1
            v = sum(1 << t for t in range(16) if m >> bin(t).count('1') & 1)
            jobs.append(('sym4-S', f'TT_4_{v}', 'full', True, 1800, 9))
            jobs.append(('sym4-noS', f'TT_4_{v}', 'full', False, 1800, 9))
    summ = open(out.replace('.csv', '_min.csv'), 'w', newline=''); sw = csv.writer(summ); sw.writerow(['stage', 'f', 'min_s', 'status'])
    def do(j):
        ms, st = ladder(j[0], j[1], j[2], j[3], j[4], j[5], w, fh)
        with lock:
            sw.writerow([j[0], j[1], '' if ms is None else ms, st]); summ.flush()
    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(do, jobs))

if __name__ == '__main__':
    main()
