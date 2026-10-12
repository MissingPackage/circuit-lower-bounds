"""WP2e stage 2 runner (see wp2e_preregistration_2026-10-12.txt).

  instance --k K --s S     enumerate E(k, s) with wp2d_enum.enum_dfs (unchanged), apply the new checker
                           (wp2e_weak1.is_weak1) and stable_check weak1 to every distinct table, append a row
                           to results_wp2e.csv (status exhaustive).  The driver wraps each call in a hard
                           timeout and writes the TIMEOUT row itself (subcommand timeout).
  timeout --k K --s S --budget B    append a TIMEOUT row
  witness                  MUX_3 witness: 3-gate circuit from find_witness, simulate.py, both checkers;
                           and the s <= 2 membership check of MUX_3 / NOT MUX_3 and of every permutation
"""
import sys, os, time, csv, json, argparse, itertools
import wp2d_enum
import stable_check
import wp2e_weak1
from simulate import check as sim_check

OUT = 'results_wp2e.csv'
FIELDS = ['k', 's', 'structures', 'leaves', 'distinct', 'weak1_new', 'weak1_stable_check', 'disagreements',
          'weak1_all_inputs_essential', 'enum_s', 'check_s', 'hits', 'status']


def append(row):
    new = not os.path.exists(OUT)
    with open(OUT, 'a', newline='') as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow(row)


def cmd_instance(k, s):
    t0 = time.time()
    found, ns, nl = wp2d_enum.enum_dfs(k, s)
    vals = sorted(found)
    t_enum = time.time() - t0
    print(f'({k},{s}) structures={ns} leaves={nl} distinct={len(vals)} enum_s={t_enum:.1f}', flush=True)
    t1 = time.time()
    tests = stable_check.tests_for('weak1', k)
    hits, dis, ess = [], [], 0
    for v in vals:
        a = wp2e_weak1.is_weak1(v, k)
        b = stable_check._holds(v, tests)
        if a != b:
            dis.append(v)
        if a:
            hits.append(v)
            ess += len(stable_check.essential_vars(v, k)) == k
    t_chk = time.time() - t1
    n_sc = sum(1 for v in vals if stable_check._holds(v, tests))
    print(f'({k},{s}) weak1_new={len(hits)} weak1_stable_check={n_sc} disagreements={len(dis)} '
          f'all_inputs_essential={ess} check_s={t_chk:.1f} first_hits={hits[:20]}', flush=True)
    append(dict(k=k, s=s, structures=ns, leaves=nl, distinct=len(vals), weak1_new=len(hits), weak1_stable_check=n_sc,
                disagreements=len(dis), weak1_all_inputs_essential=ess, enum_s=round(t_enum, 1),
                check_s=round(t_chk, 1), hits=' '.join(map(str, hits[:20])), status='exhaustive'))
    return 0


def cmd_timeout(k, s, budget):
    append(dict(k=k, s=s, structures='', leaves='', distinct='', weak1_new='', weak1_stable_check='',
                disagreements='', weak1_all_inputs_essential='', enum_s='', check_s='', hits='',
                status=f'TIMEOUT {budget} s'))
    return 0


def permute(tt, k, perm):
    """table of g'(x) = g(x_perm), i.e. input i of g' is input perm[i] of g"""
    out = 0
    for t in range(1 << k):
        bits = [(t >> i) & 1 for i in range(k)]
        src = sum(bits[perm[i]] << i for i in range(k))
        out |= ((tt >> t) & 1) << src
    return out


def cmd_witness():
    ok = True
    mux = wp2e_weak1.tt_of(3, lambda x: x[1] if x[0] else x[2])
    full = (1 << 8) - 1
    orbit = sorted({permute(t, 3, p) for t in (mux, full ^ mux) for p in itertools.permutations(range(3))})
    print(f'MUX_3 tt={mux}, NOT MUX_3 tt={full ^ mux}; orbit under input permutation and output negation: {orbit}')
    for k, s in [(2, 1), (2, 2), (3, 1), (3, 2)]:
        e, _, _ = wp2d_enum.enum_dfs(k, s)
        if k == 3:
            inter = sorted(e & set(orbit))
            print(f'E({k},{s}): {len(e)} tables, intersection with the MUX_3 orbit: {inter}')
            ok &= not inter
        else:
            print(f'E({k},{s}): {len(e)} tables (2 inputs, cannot contain a 3-input essential function)')
    w = wp2d_enum.find_witness(3, 3, mux)
    if w is None:
        w = wp2d_enum.find_witness(3, 3, full ^ mux); neg = True
    else:
        neg = False
    circ = wp2d_enum.to_wp1_circuit(3, *w)
    if neg:   # absorb the output negation into the top gate type
        j, kk, f = circ['gates'][-1]
        circ['gates'][-1] = [j, kk, [1 - b for b in f]]
    text = wp2d_enum.circuit_text(3, *w) + (' (output negated)' if neg else '')
    tt_bits = [(mux >> t) & 1 for t in range(8)]
    sim = sim_check(circ, [tt_bits])
    sc = stable_check.circuit_tt(circ) == mux
    new = wp2e_weak1.is_weak1(mux, 3)
    old = stable_check.holds(mux, 3, 'weak1')
    print(f'witness circuit (3 gates): {json.dumps(circ)}')
    print(f'  {text}')
    print(f'  simulate.py={sim} stable_check.circuit_tt==tt: {sc} new checker weak1={new} stable_check weak1={old}')
    ok &= sim and sc and new and old and len(circ['gates']) == 3
    print('witness', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cmd', choices=['instance', 'timeout', 'witness'])
    ap.add_argument('--k', type=int); ap.add_argument('--s', type=int); ap.add_argument('--budget', type=int)
    a = ap.parse_args()
    if a.cmd == 'instance':
        return cmd_instance(a.k, a.s)
    if a.cmd == 'timeout':
        return cmd_timeout(a.k, a.s, a.budget)
    return cmd_witness()


if __name__ == '__main__':
    sys.exit(main())
