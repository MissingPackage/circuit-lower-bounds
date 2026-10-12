"""Negative controls for the certificate checker (WP3.1, pre-registration D8).

Each control copies the Cases 1-5 certificates, injects one corruption, and runs
the checker on the node(s) the corruption affects.  A control passes if the
checker rejects, and the machine-stated reason names the injected corruption
(matched by the expected keyword).

Usage: python -m gecheck.mutants CERT_DIR OUT_DIR LOG.json
"""
import copy
import json
import os
import shutil
import sys

from . import checker as ck


def load(cert_dir):
    d = {}
    for fn in sorted(os.listdir(cert_dir)):
        if fn.endswith('.json'):
            with open(os.path.join(cert_dir, fn)) as f:
                spec = json.load(f)
            d[spec['id']] = spec
    return d


def m_wrong_gain_4(d):
    d['4']['actions'][0]['types'] = [3]
    return ['4'], 'below types [3]', 'Case 4 claims type 3 (four gates) instead of type 2'


def m_wrong_gain_1a(d):
    d['1a']['actions'][0]['types'] = [3]
    return ['1a'], 'below types [3]', 'Case 1a claims type 3 instead of type 7'


def m_wrong_gain_2(d):
    d['2']['actions'][0]['types'] = [7]
    return ['2'], 'below types [7]', 'Case 2 claims type 7 (two gates) instead of type 2'


def m_wrong_gain_3_type4(d):
    d['3']['actions'][0]['types'] = [4]
    return ['3'], 'below types [4]', 'Case 3 claims type 4 instead of type 3'


def m_wrong_subst_var_4(d):
    d['4']['actions'][0]['steps'][0]['var'] = 'x'
    return ['4'], 'below types [2]', 'Case 4 substitutes x (the 1-variable) instead of y'


def m_wrong_subst_var_2(d):
    d['2']['actions'][0]['steps'][0]['var'] = 'x'
    return ['2'], 'below types [2]', 'Case 2 substitutes the 0-variable x instead of its partner'


def m_fixed_constant_4(d):
    d['4']['actions'][0]['steps'][0]['value'] = 0
    return ['4'], 'below types [2]', 'Case 4 uses the fixed constant y <- 0 instead of the trivialising one'


def m_wrong_kind_1a(d):
    s = d['1a']['actions'][0]['steps'][0]
    s['kind'] = 'affine'
    s['src'] = 'x'
    return ['1a'], 'illegal', 'Case 1a uses an affine substitution of a protected variable'


def m_quadratic_from_var_51(d):
    for a in d['5.1']['actions']:
        for s in a['steps']:
            if s['kind'] == 'affine':
                s['kind'] = 'quadratic'
    d['5.1']['actions'] = [a for a in d['5.1']['actions'] if a['steps'][0]['kind'] == 'quadratic']
    return ['5.1'], 'illegal', 'Case 5.1 makes a quadratic substitution whose source is an input (illegal rdq step)'


def m_weakened_pattern_4(d):
    del d['4']['pattern']['nodes']['x']['out']
    return ['4'], 'not discharged', 'Case 4 pattern drops out(x) = 1'


def m_dropped_pre_4(d):
    d['4']['pre'] = ['2', '3']
    return ['4'], 'not discharged', 'Case 4 drops the precondition "not Case 1" (x may be protected)'


def m_missing_leaf_root_4(d):
    d['R']['children'] = [c for c in d['R']['children'] if c != '4']
    return ['R'], 'uncovered completion', 'Case 4 removed from the root case list (missing leaf)'


def m_missing_leaf_root_3(d):
    d['R']['children'] = [c for c in d['R']['children'] if c != '3']
    return ['R'], 'uncovered completion', 'Case 3 removed from the root case list (missing leaf)'


def m_bad_symmetry_5(d):
    d['5']['symmetries'] = [{'x': 'y', 'y': 'x'}]
    return ['5'], 'not an automorphism', 'Case 5 declares x <-> y without B <-> C'


def m_trivialise_wrong_target_1b(d):
    d['1b']['actions'][0]['steps'][0]['value'] = {'trivialize': 'x'}
    return ['1b'], 'does not trivialise', 'Case 1b trivialises the wrong node'


CONTROLS = [m_wrong_gain_4, m_wrong_gain_1a, m_wrong_gain_2, m_wrong_gain_3_type4,
            m_wrong_subst_var_4, m_wrong_subst_var_2, m_fixed_constant_4, m_wrong_kind_1a,
            m_quadratic_from_var_51, m_weakened_pattern_4, m_dropped_pre_4,
            m_missing_leaf_root_4, m_missing_leaf_root_3, m_bad_symmetry_5,
            m_trivialise_wrong_target_1b]


def run(cert_dir, out_dir, logpath):
    base = load(cert_dir)
    rows = []
    for ctl in CONTROLS:
        d = copy.deepcopy(base)
        nodes_to_check, keyword, desc = ctl(d)
        mdir = os.path.join(out_dir, ctl.__name__)
        if os.path.exists(mdir):
            shutil.rmtree(mdir)
        os.makedirs(mdir)
        for k, v in d.items():
            with open(os.path.join(mdir, 'case_%s.json' % k), 'w') as f:
                json.dump(v, f, indent=1)
        verdicts = []
        try:
            nodes = ck.load_tree(mdir)
            for nid in nodes_to_check:
                res = ck.check_node(nodes, nodes[nid])
                st, why = ck.status_of(res)
                verdicts.append((nid, st, why))
        except ck.CertificateError as e:
            verdicts.append(('load', 'rejected', str(e)))
        except ValueError as e:
            verdicts.append(('load', 'rejected', 'invalid certificate: %s' % e))
        rejected = any(v[1] == 'rejected' for v in verdicts)
        accepted = all(v[1] == 'verified' for v in verdicts)
        named = any(v[1] == 'rejected' and keyword in v[2] for v in verdicts)
        row = {'control': ctl.__name__, 'corruption': desc, 'checked': nodes_to_check,
               'outcome': 'rejected' if rejected else ('ACCEPTED' if accepted else 'not-decided'),
               'reason_names_corruption': named, 'expected_keyword': keyword,
               'verdicts': verdicts}
        rows.append(row)
        print('%-32s %-11s named=%-5s %s' % (ctl.__name__, row['outcome'], named,
                                             (verdicts[0][2] if verdicts else '')[:300]), flush=True)
    with open(logpath, 'w') as f:
        json.dump(rows, f, indent=1)
    return rows


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2], sys.argv[3])
