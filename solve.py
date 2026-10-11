"""Run one (function, s) instance in a child process with a hard wall-clock timeout."""
import multiprocessing as mp, time, json
from funcs import build

SOLVER = 'cadical195'

def is_symmetric(n, outs):
    def perm(tt, i):
        r = []
        for t in range(1 << n):
            a, b = (t >> i) & 1, (t >> (i + 1)) & 1
            t2 = t & ~(3 << i) | (b << i) | (a << (i + 1))
            r.append(tt[t2])
        return r
    return all(perm(tt, i) == tt for tt in outs for i in range(n - 1))

def _work(name, s, mode, sym, q):
    from pysat.solvers import Solver
    from encoder import Enc
    from simulate import check
    n, outs = build(name)
    e = Enc(n, outs, s, mode=mode, sym=sym)
    t0 = time.time()
    with Solver(name=SOLVER, bootstrap_with=e.cl) as S:
        sat = S.solve()
        model = S.get_model() if sat else None
    dt = time.time() - t0
    if not sat:
        q.put(dict(res='UNSAT', solve_s=dt, vars=e.nv, clauses=len(e.cl), sim='', circuit=''))
        return
    circ = e.decode(model)
    ok = check(circ, outs)
    q.put(dict(res='SAT', solve_s=dt, vars=e.nv, clauses=len(e.cl), sim='pass' if ok else 'FAIL', circuit=json.dumps(circ)))

def run(name, s, mode='full', sym='auto', timeout=60):
    n, outs = build(name)
    if sym == 'auto':
        sym = mode == 'full' and is_symmetric(n, outs)
    q = mp.Queue()
    p = mp.Process(target=_work, args=(name, s, mode, sym, q))
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
        r = dict(res='TIMEOUT' if alive else 'ERROR', solve_s='', vars='', clauses='', sim='', circuit='')
    else:
        p.join()
    r.update(f=name, n=n, s=s, mode=mode, sym=int(bool(sym)), wall_s=round(wall, 3), timeout_s=timeout)
    return r
