"""WP2d stage E: rerun the reviewer's enumerator (wp2d/reviewer_scripts/topo.py + evalp.py, verbatim,
unreviewed) on the main instances, dump its truth-table sets, and compare them with mine
(wp2d/E_k_s.npy) as sets: equality, inclusion (mine subset of theirs: the reviewer's topologies() has
no canonical topological-order rule, so it visits every first-use labelling of a DAG; mine visits a
subset of those labellings), and equality of the canonical forms under input permutation (k <= 6,
wp2d_canon.canon).  Output: results_wp2d_compare.csv, wp2d/R_k_s.npy (reviewer sets).
"""
import sys, os, time, csv
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wp2d', 'reviewer_scripts'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import topo, evalp                     # reviewer's modules
import wp2d_enum, wp2d_canon

REPORTED = {(6, 5): 29005, (6, 6): 1857928, (7, 6): 437025}
T0 = time.time()


def log(*a):
    print('%7.1fs' % (time.time() - T0), *a, flush=True)


def main():
    rows = []
    for k, s in [(4, 4), (5, 5), (6, 5), (7, 6), (6, 6)]:
        t0 = time.time()
        T, U = evalp.all_tts(k, s)
        R = wp2d_enum.ints_to_arr(U, k)
        np.save(f'wp2d/R_{k}_{s}.npy', R)
        M = np.load(f'wp2d/E_{k}_{s}.npy')
        my_structs = wp2d_enum.count_structures(k, s)
        if R.ndim == 1:
            equal = np.array_equal(R, M)
            mine_in_theirs = len(np.setdiff1d(M, R)) == 0
            theirs_minus_mine = int(len(np.setdiff1d(R, M)))
        else:
            sR = set(map(tuple, R.tolist())); sM = set(map(tuple, M.tolist()))
            equal = sR == sM
            mine_in_theirs = sM <= sR
            theirs_minus_mine = len(sR - sM)
        canon_equal = ''
        nc_mine = nc_theirs = -1
        if k <= 6 and not equal:
            cm = wp2d_canon.canon(M.copy(), k)
            ct = wp2d_canon.canon(R.copy(), k)
            canon_equal = int(np.array_equal(cm, ct))
            nc_mine, nc_theirs = len(cm), len(ct)
            np.save(f'wp2d/C_{k}_{s}_reviewer.npy', ct)
        elif k <= 6:
            canon_equal = 1
        rep = REPORTED.get((k, s), '')
        log(f'({k},{s}) reviewer: topologies={len(T)} distinct={len(U)} reported={rep} reproduced={int(len(U) == rep) if rep else ""} | '
            f'mine: structures={my_structs} distinct={len(M)} | equal={int(equal)} mine_subset_of_theirs={int(mine_in_theirs)} '
            f'theirs_minus_mine={theirs_minus_mine} canonical_classes mine={nc_mine} theirs={nc_theirs} canon_equal={canon_equal} ({time.time() - t0:.1f} s)')
        rows.append(dict(k=k, s=s, reviewer_topologies=len(T), reviewer_distinct=len(U), reviewer_reported=rep,
                         reported_reproduced=int(len(U) == rep) if rep else '', my_structures=my_structs, my_distinct=len(M),
                         sets_equal=int(equal), mine_subset_of_theirs=int(mine_in_theirs), theirs_minus_mine=theirs_minus_mine,
                         canonical_mine=nc_mine, canonical_theirs=nc_theirs, canonical_equal=canon_equal,
                         status='reviewer set reproduced here from the verbatim scripts'))
        with open('results_wp2d_compare.csv', 'w', newline='') as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader(); w.writerows(rows)
    return 0


if __name__ == '__main__':
    sys.exit(main())
