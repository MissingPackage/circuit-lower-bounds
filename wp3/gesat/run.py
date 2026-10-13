"""WP3.2 driver: one SAT counterexample search per certificate node (and per
identification partition), replay of SAT answers with the WP3.1 engine, one
result file per certificate written as soon as it finishes.

Usage (from wp3/):
  python -m gesat.run CERT_DIR OUT_DIR ID [ID ...] [--fb 16] [--timeout 600]
                      [--replay 120] [--tag NAME]
"""
import argparse
import gzip
import json
import os
import sys
import threading
import time

from pysat.solvers import Solver

from gecheck import checker as ck
from .encoder import Instance
from . import replay as rp

FB_MAX = 32


def _child(clauses, budget, out_path, want_proof):
    s = Solver(name='cadical195', bootstrap_with=clauses, with_proof=want_proof)
    r = s.solve()
    res = {'r': r, 'model': s.get_model() if r is True else None}
    if r is False and want_proof:
        with gzip.open(out_path + '.drat.gz', 'wt') as f:
            for line in s.get_proof():
                f.write(line + '\n')
    with open(out_path, 'w') as f:
        json.dump(res, f)


def solve(I, budget, proof_path):
    """Solve in a forked child with a hard timeout (the in-process interrupt does
    not fire while CaDiCaL holds the interpreter)."""
    import multiprocessing as mp
    import tempfile
    ctx = mp.get_context('fork')
    tmp = tempfile.mktemp(prefix='wp32_', dir='/tmp')
    p = ctx.Process(target=_child, args=(I.c.clauses, budget, tmp, proof_path is not None))
    t0 = time.time()
    p.start()
    p.join(max(budget, 0.1))
    if p.is_alive():
        p.kill()
        p.join()
        dt = time.time() - t0
        for f in (tmp, tmp + '.drat.gz'):
            if os.path.exists(f):
                os.remove(f)
        return None, dt, None, None
    dt = time.time() - t0
    with open(tmp) as f:
        res = json.load(f)
    os.remove(tmp)
    drat = None
    if res['r'] is False and proof_path:
        os.makedirs(os.path.dirname(proof_path), exist_ok=True)
        os.replace(tmp + '.drat.gz', proof_path)
        with gzip.open(proof_path, 'rt') as f:
            nlines = sum(1 for _ in f)
        drat = {'file': proof_path, 'lines': nlines}
    return res['r'], dt, res['model'], drat


def run_node(cert_dir, nid, out_dir, fb0, timeout, replay_s, tag=None, log=print, siblings=False):
    try:
        tree = ck.load_tree(cert_dir)
    except ck.CertificateError as e:
        rec = {'id': tag or nid, 'node': nid, 'cert_dir': cert_dir, 'status': 'REJECTED-STRUCTURAL',
               'reason': str(e), 'solve_s': 0.0, 'encode_s': 0.0, 'n_vars': 0, 'n_clauses': 0,
               'drat_status': None}
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, '%s.json' % (tag or nid)), 'w') as f:
            json.dump(rec, f, indent=1)
        return rec
    n = tree[nid]
    mode = 'leaf' if n.kind == 'leaf' else 'internal'
    parts = ck.initial_comps(n)
    t_start = time.time()
    rec = {'id': tag or nid, 'node': nid, 'cert_dir': cert_dir, 'kind': n.kind, 'mode': mode,
           'paper_leaf': n.paper_leaf, 'claimed_types': sorted(set(t for a in n.actions for t in a['types'])),
           'partitions': [], 'status': None, 'solve_s': 0.0, 'encode_s': 0.0, 'n_vars': 0, 'n_clauses': 0,
           'drat_status': None, 'timeout_s': timeout, 'siblings': siblings}
    status = 'UNSAT'
    for pi, comp in enumerate(parts):
        fb = fb0
        while True:
            remaining = timeout - rec['solve_s']
            t0 = time.time()
            I = Instance(tree, n, comp, fb, mode=mode, siblings=siblings)
            enc = time.time() - t0
            nv, ncl = I.c.n, len(I.c.clauses)
            log('  [%s] partition %d/%d FB=%d: %d vars %d clauses, encoded in %.1f s; solving (budget %.0f s)'
                % (nid, pi + 1, len(parts), fb, nv, ncl, enc, remaining), flush=True)
            proof_path = os.path.join(out_dir, 'proofs', '%s.p%d.drat.gz' % (tag or nid, pi))
            r, dt, model, drat = solve(I, remaining, proof_path)
            rec['solve_s'] += dt
            rec['encode_s'] += enc
            rec['n_vars'] += nv
            rec['n_clauses'] += ncl
            prow = {'partition': pi, 'pattern': comp.describe(), 'FB': fb, 'n_vars': nv, 'n_clauses': ncl,
                    'encode_s': round(enc, 2), 'solve_s': round(dt, 2), 'n_sims': len(I.sims), 'KA': I.KA}
            if r is None:
                prow['status'] = 'timeout'
                rec['partitions'].append(prow)
                status = 'timeout'
                break
            if r is False:
                prow['status'] = 'UNSAT'
                prow['drat'] = drat
                rec['partitions'].append(prow)
                log('  [%s] partition %d: UNSAT in %.1f s (proof %d lines)' % (nid, pi + 1, dt, drat['lines']),
                    flush=True)
                break
            view = rp.decode(I, model)
            ovf = rp.val(model, I.ovf)
            prow['view'] = view
            prow['sims'] = rp.sim_summary(I, model)
            if ovf:
                prow['status'] = 'OVF'
                rec['partitions'].append(prow)
                log('  [%s] partition %d: OVF model at FB=%d' % (nid, pi + 1, fb), flush=True)
                if fb < FB_MAX and rec['solve_s'] < timeout:
                    fb = 2 if fb == 0 else fb * 2
                    continue
                status = 'OVF' if status == 'UNSAT' else status
                break
            prow['status'] = 'SAT'
            comp2 = rp.to_comp(I, view)
            prow['engine_comp'] = comp2.describe()
            rpl = rp.replay(tree, n, comp2, replay_s)
            prow['replay'] = rpl
            rec['partitions'].append(prow)
            log('  [%s] partition %d: SAT in %.1f s, replay verdict %s' % (nid, pi + 1, dt, rpl['verdict']),
                flush=True)
            status = 'SAT'
            break
        if status in ('SAT', 'timeout'):
            break
    rec['status'] = status
    rec['solve_s'] = round(rec['solve_s'], 2)
    rec['encode_s'] = round(rec['encode_s'], 2)
    rec['wall_s'] = round(time.time() - t_start, 2)
    if status == 'UNSAT':
        rec['certified_types'] = rec['claimed_types'] if n.kind == 'leaf' else None
        rec['drat_status'] = 'unsat-uncertified (DRAT proof emitted, no external checker available offline)'
    if status == 'SAT':
        sat = [p for p in rec['partitions'] if p['status'] == 'SAT'][-1]
        rec['counter_completion'] = sat['view']
        rec['replay_verdict'] = sat['replay']['verdict']
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, '%s.json' % (tag or nid)), 'w') as f:
        json.dump(rec, f, indent=1, default=str)
    return rec


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('cert_dir')
    ap.add_argument('out_dir')
    ap.add_argument('ids', nargs='+')
    ap.add_argument('--fb', type=int, default=0)
    ap.add_argument('--timeout', type=float, default=600.0)
    ap.add_argument('--replay', type=float, default=120.0)
    ap.add_argument('--tag', default=None)
    a = ap.parse_args(argv)
    for i, nid in enumerate(a.ids):
        print('[%d/%d] %s' % (i + 1, len(a.ids), nid), flush=True)
        rec = run_node(a.cert_dir, nid, a.out_dir, a.fb, a.timeout, a.replay, a.tag if len(a.ids) == 1 else None)
        print('[%d/%d] %s -> %s  solve %.1f s  encode %.1f s  vars %d  clauses %d%s' % (
            i + 1, len(a.ids), nid, rec['status'], rec['solve_s'], rec['encode_s'], rec['n_vars'],
            rec['n_clauses'], ('  replay ' + rec['replay_verdict']) if rec.get('replay_verdict') else ''),
            flush=True)


if __name__ == '__main__':
    main(sys.argv[1:])
