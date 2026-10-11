"""WP2 campaign runner.  usage: run_wp2.py --out results_wp2_<stage>.csv --job SPEC [--job SPEC ...] [--workers 2]
SPEC = variant:k:mode:essential:smin:smax:timeout_s      e.g.  stable1:5:full:0:0:11:7200
Each job is a ladder s = smin..smax on one (variant, k, mode, essential); the ladder stops at the first SAT or
at the first non-UNSAT outcome (TIMEOUT/ERROR is recorded as such and never as UNSAT).  Every instance is one
child process with a hard wall-clock timeout (solve_wp2.run).  Rows are appended to --out (header written if
the file is new) so that stages accumulate; a *_min.csv summary is written per run.
Presets: --preset k34 | k5 | k6 expand to the pre-registered job lists (see wp2_preregistration_2026-10-11.txt).
"""
import csv, os, argparse, threading, time
from concurrent.futures import ThreadPoolExecutor
from solve_wp2 import run

FIELDS = ['variant', 'k', 's', 'mode', 'essential', 'res', 'wall_s', 'timeout_s', 'solve_s', 'vars', 'clauses',
          'aux_vars', 'sim', 'checker', 'tt', 'circuit']
lock = threading.Lock()

PRESETS = {
    'k34': ['stable1:3:full:0:0:4:1800', 'stable1:4:full:0:0:7:1800',
            'weak1:3:full:0:0:3:1800', 'weak1:3:none:0:0:3:1800',
            'weak1:4:full:0:0:3:1800', 'weak1:4:full:1:0:4:1800',
            'stable2:3:full:0:0:4:1800', 'stable2:4:full:0:0:7:1800',
            'stable1:3:none:0:0:4:1800', 'stable1:4:none:0:0:7:1800'],
    'k5':  ['fixed_gst1:5:full:0:0:11:7200', 'stable1:5:full:0:0:11:7200',
            'weak1:5:full:0:0:3:7200', 'weak1:5:full:1:0:5:7200', 'stable2:5:full:0:0:10:7200',
            'stable1pos:5:full:0:11:11:7200'],
    'k6':  ['weak1:6:full:0:0:3:7200', 'weak1:6:full:1:0:6:7200', 'stable1:6:full:0:0:10:7200',
            'stable2:6:full:0:0:10:7200'],
}


def parse(spec):
    v, k, mode, ess, smin, smax, to = spec.split(':')
    return dict(variant=v, k=int(k), mode=mode, essential=bool(int(ess)), smin=int(smin), smax=int(smax), timeout=float(to))


def ladder(j, w, fh, deadline):
    for s in range(j['smin'], j['smax'] + 1):
        if deadline and time.time() > deadline:
            with lock:
                print(time.strftime('%H:%M:%S'), j['variant'], 'k=%d' % j['k'], 's=%d' % s, 'SKIPPED (run deadline)', flush=True)
            return None, 'SKIPPED@%d' % s
        to = j['timeout']
        if deadline:
            to = max(1.0, min(to, deadline - time.time()))
        r = run(j['variant'], j['k'], s, mode=j['mode'], essential=j['essential'], timeout=to)
        with lock:
            w.writerow({f: r.get(f, '') for f in FIELDS}); fh.flush()
            print(time.strftime('%H:%M:%S'), j['variant'], 'k=%d' % j['k'], 's=%d' % s, j['mode'], 'ess=%d' % r['essential'],
                  r['res'], r['sim'], r['checker'], 'tt=%s' % r['tt'], '%.1fs' % r['wall_s'], 'to=%.0f' % r['timeout_s'], flush=True)
        if r['res'] == 'SAT':
            return s, 'SAT'
        if r['res'] != 'UNSAT':
            return None, r['res'] + '@%d' % s
    return None, 'UNSAT<=%d' % j['smax']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True); ap.add_argument('--job', action='append', default=[])
    ap.add_argument('--preset', action='append', default=[]); ap.add_argument('--workers', type=int, default=2)
    ap.add_argument('--deadline-min', type=float, default=0, help='stop launching new instances after this many minutes; '
                    'running instances are cut at the deadline and recorded as TIMEOUT with the reduced timeout_s')
    a = ap.parse_args()
    specs = [s for p in a.preset for s in PRESETS[p]] + a.job
    jobs = [parse(s) for s in specs]
    new = not os.path.exists(a.out)
    fh = open(a.out, 'a', newline=''); w = csv.DictWriter(fh, fieldnames=FIELDS)
    if new:
        w.writeheader(); fh.flush()
    summ = open(a.out.replace('.csv', '_min.csv'), 'a', newline=''); sw = csv.writer(summ)
    if os.path.getsize(summ.name) == 0:
        sw.writerow(['variant', 'k', 'mode', 'essential', 'min_s', 'status'])
    deadline = time.time() + a.deadline_min * 60 if a.deadline_min else None

    def do(j):
        ms, st = ladder(j, w, fh, deadline)
        with lock:
            sw.writerow([j['variant'], j['k'], j['mode'], int(j['essential']), '' if ms is None else ms, st]); summ.flush()
    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(do, jobs))


if __name__ == '__main__':
    main()
