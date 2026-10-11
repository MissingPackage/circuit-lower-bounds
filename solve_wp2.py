"""WP2 per-instance solver: one (variant, k, s) instance in a child process with a hard wall-clock timeout.
Same structure as solve.py (WP1); the free-function variants use encoder.Enc with an integer `outs` plus
the constraints of stability.py, the fixed variant uses the WP1 path unchanged.

variant: fixed_gst1 | stable1 | stable1pos | weak1 | stable2
After SAT: the decoded circuit is (1) re-simulated row by row by simulate.check against the truth table the
solver claims (sim pass/FAIL) and (2) handed to the independent checker stable_check (own bit-parallel
simulation, own definition code), whose verdict accept/reject refers to the property searched.
"""
import multiprocessing as mp, time, json
from solve import SOLVER

GST1_INT = 376339136   # GHKK Lemma 4 truth table, see sources/GHKK_TRANSCRIPTION_2026-10-11.txt


def _work(variant, k, s, mode, essential, q):
    from pysat.solvers import Solver
    from encoder import Enc
    from simulate import check
    import stability, stable_check
    if variant == 'fixed_gst1':
        from funcs import build
        n, outs = build(f'TT_5_{GST1_INT}')
        assert n == k == 5
        e = Enc(n, outs, s, mode=mode, sym=False)
        aux = 0
    else:
        e = Enc(k, 1, s, mode=mode, sym=False, sgnfree=(variant == 'stable1pos'))
        aux = stability.add_variant(e, variant, essential_inputs=essential)
    t0 = time.time()
    with Solver(name=SOLVER, bootstrap_with=e.cl) as S:
        sat = S.solve()
        model = S.get_model() if sat else None
    dt = time.time() - t0
    base = dict(solve_s=round(dt, 3), vars=e.nv, clauses=len(e.cl), aux_vars=aux)
    if not sat:
        q.put(dict(res='UNSAT', sim='', checker='', tt='', circuit='', **base)); return
    circ = e.decode(model)
    if variant == 'fixed_gst1':
        tts = outs
    else:
        tts = circ.pop('tt')
    ok = check(circ, tts)                                   # WP1 simulator vs claimed truth table
    tt_int = stable_check.circuit_tt(circ)                  # independent simulation
    claimed = sum(b << t for t, b in enumerate(tts[0]))
    prop = 'stable1' if variant == 'fixed_gst1' else variant
    verdict = 'accept' if (tt_int == claimed and stable_check.holds(tt_int, k, prop, essential)) else 'reject'
    q.put(dict(res='SAT', sim='pass' if ok else 'FAIL', checker=verdict, tt=tt_int, circuit=json.dumps(circ), **base))


def run(variant, k, s, mode='full', essential=False, timeout=60):
    q = mp.Queue()
    p = mp.Process(target=_work, args=(variant, k, s, mode, essential, q))
    t0 = time.time(); p.start()
    r = None
    try:
        r = q.get(timeout=timeout)
    except Exception:
        pass
    wall = time.time() - t0
    if r is None:
        alive = p.is_alive()
        p.kill(); p.join()
        r = dict(res='TIMEOUT' if alive else 'ERROR', solve_s='', vars='', clauses='', aux_vars='', sim='', checker='', tt='', circuit='')
    else:
        p.join()
    r.update(variant=variant, k=k, s=s, mode=mode, essential=int(bool(essential)), wall_s=round(wall, 3), timeout_s=timeout)
    return r
