"""WP2c: verification ladder for SAT rows (the brief's three checks on a found function).
usage: wp2c_verify_sat.py --in results_wp2c.csv [--variant stable1] [--timeout 3600] [--log log_wp2c_sat.txt]
For every row with res = SAT: (1) simulate.check of the decoded circuit against the claimed truth table,
(2) stable_check.holds on the independent bit-parallel truth table of the circuit, (3) the fixed-function
WP1 encoder (solve.run on TT_k_<int>) at s' = 0..s in mode full (expected UNSAT below s, SAT at s) and at
s - 1 and s in mode none (expected UNSAT, SAT).  TIMEOUT is reported as TIMEOUT, never as UNSAT.
Exit status 0 iff every SAT row passes all three checks (or there is no SAT row).
"""
import argparse, csv, json, sys
import simulate, stable_check
from solve import run as run_fixed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', required=True); ap.add_argument('--variant', default=None)
    ap.add_argument('--timeout', type=float, default=3600); ap.add_argument('--log', default='log_wp2c_sat.txt')
    a = ap.parse_args()
    rows = [r for r in csv.DictReader(open(a.inp)) if r['res'] == 'SAT']
    out = open(a.log, 'a')

    def log(*x):
        s = ' '.join(str(v) for v in x); print(s, flush=True); out.write(s + '\n'); out.flush()

    ok_all = True
    log('verify', a.inp, 'SAT rows:', len(rows))
    for r in rows:
        k, s, mode = int(r['k']), int(r['s']), r['mode']
        variant = a.variant or r['variant']
        if not r['tt'] or variant.startswith('fixed_'):
            log(f'row {variant} k={k} s={s} mode={mode}: fixed-function row, no claimed truth table, skipped')
            continue
        circ = json.loads(r['circuit']); tt = int(r['tt'])
        tts = [[(tt >> t) & 1 for t in range(1 << k)]]
        sim = simulate.check(circ, tts)
        ind = stable_check.circuit_tt(circ)
        chk = ind == tt and stable_check.holds(tt, k, variant, False)
        log(f'row {variant} k={k} s={s} mode={mode} tt={tt} sim={"pass" if sim else "FAIL"} independent_tt_match={ind == tt} checker={"accept" if chk else "reject"}')
        ladder_ok = True
        name = f'TT_{k}_{tt}'
        for sp in range(0, s + 1):
            rr = run_fixed(name, sp, mode='full', sym=False, timeout=a.timeout)
            log(f'  fixed {name} mode=full s={sp} {rr["res"]} wall={rr["wall_s"]:.1f}s sim={rr["sim"]}')
            want = 'SAT' if sp == s else 'UNSAT'
            if rr['res'] != want or (want == 'SAT' and rr['sim'] != 'pass'):
                ladder_ok = False
        for sp in (s - 1, s):
            if sp < 0:
                continue
            rr = run_fixed(name, sp, mode='none', sym=False, timeout=a.timeout)
            log(f'  fixed {name} mode=none s={sp} {rr["res"]} wall={rr["wall_s"]:.1f}s sim={rr["sim"]}')
            want = 'SAT' if sp == s else 'UNSAT'
            if rr['res'] != want or (want == 'SAT' and rr['sim'] != 'pass'):
                ladder_ok = False
        verdict = sim and chk and ladder_ok
        log(f'  verdict: {"VERIFIED" if verdict else "NOT VERIFIED"} (sim={sim}, checker={chk}, ladder={ladder_ok})')
        ok_all = ok_all and verdict
    log('all SAT rows verified:', ok_all)
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main())
