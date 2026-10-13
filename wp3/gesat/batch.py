"""WP3.2 batch lists (certificates and negative controls).

Usage (from wp3/): python -m gesat.batch {leaves|controls_internal} [--fb 8]
Each item writes wp3/logs/wp32/<id>.json when it finishes.
"""
import sys
import time

from . import run

LEAVES = ['1a', '1b', '2', '4', '5.1', '5.2.1', '5.2.2', '5.3', '5.4.1.1.0', '5.4.1.1.1', '5.4.1.1.2',
          '5.4.1.2', '5.4.1.3', '5.4.1.4', '5.4.2.1', '5.4.2.2', '3']
INTERNAL = ['5.2', '5.4.2', '5.4.1.1', '5.4.1', '5.4', '5']
# control -> node checked (as in gecheck/mutants.py)
CONTROLS = [('m_wrong_gain_4', '4'), ('m_wrong_gain_1a', '1a'), ('m_wrong_gain_2', '2'),
            ('m_wrong_subst_var_4', '4'), ('m_wrong_subst_var_2', '2'), ('m_fixed_constant_4', '4'),
            ('m_wrong_kind_1a', '1a'), ('m_quadratic_from_var_51', '5.1'), ('m_weakened_pattern_4', '4'),
            ('m_dropped_pre_4', '4'), ('m_missing_leaf_root_4', 'R'), ('m_missing_leaf_root_3', 'R'),
            ('m_bad_symmetry_5', '5'), ('m_trivialise_wrong_target_1b', '1b'), ('m_wrong_gain_3_type4', '3')]
OUT = 'logs/wp32'


def main(argv):
    which = argv[0]
    fb = int(argv[argv.index('--fb') + 1]) if '--fb' in argv else 8
    if which == 'leaves':
        items = [('certs', i, None) for i in LEAVES]
    elif which == 'internal':
        items = [('certs', i, None) for i in INTERNAL]
    elif which == 'controls':
        items = [('mutants/' + m, i, m) for m, i in CONTROLS]
    elif which == 'controls_internal':
        items = [('mutants/' + m, i, m) for m, i in CONTROLS] + [('certs', i, None) for i in INTERNAL]
    else:
        items = [('certs', i, None) for i in argv[1:] if not i.startswith('--')]
    t0 = time.time()
    for k, (d, nid, tag) in enumerate(items):
        print('[%d/%d, %.0f s elapsed, %d items left] %s %s' % (k + 1, len(items), time.time() - t0,
                                                              len(items) - k, tag or nid, d), flush=True)
        rec = run.run_node(d, nid, OUT, fb, 600.0, 120.0, tag)
        print('    -> %s solve %.1f s encode %.1f s vars %d clauses %d %s' % (
            rec['status'], rec['solve_s'], rec['encode_s'], rec['n_vars'], rec['n_clauses'],
            rec.get('replay_verdict', '') or rec.get('reason', '')), flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
