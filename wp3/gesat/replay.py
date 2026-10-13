"""Decode a SAT model into a revealed completion and replay it with the WP3.1
engine (gecheck.engine / gecheck.checker, unmodified) as an independent check.

Verdicts: 'violation'        the engine finds a completion extending the model
                             that it does not discharge (leaf) / cover (internal);
          'not-a-violation'  every extension is discharged, covered, vacuous or
                             pruned by the engine (the SAT answer was spurious);
          'undecided'        the engine's DFS did not finish in the budget.
"""
import time

from gecheck import checker as ck
from gecheck.engine import Comp, Need
from .cnf import TRUE, FALSE


def val(model, lit):
    if lit == TRUE:
        return True
    if lit == FALSE:
        return False
    v = model[abs(lit) - 1] > 0
    return v if lit > 0 else not v


def decode(I, model):
    """Revealed view: list of slot records."""
    view = []
    names = {}
    for nm, nid in I.comp.names.items():
        names.setdefault(I.pid2slot[nid], []).append(nm)
    for s in range(I.N):
        if not val(model, I.used[s]):
            continue
        isg = val(model, I.isg[s])
        od = [d for d in range(I.cap + 1) if val(model, I.od[s][d])]
        rec = {'slot': s, 'block': I.blk[s], 'names': names.get(s, []),
               'kind': 'gate' if isg else 'var', 'out': od[0] if od else None}
        if isg:
            rec['type'] = 'and' if val(model, I.isand[s]) else 'xor'
            rec['bits'] = [int(val(model, b)) for b in I.bit[s]]
            rec['full'] = val(model, I.full[s])
            ins = []
            for j in (0, 1):
                t = [v for v, l in I.inp[(s, j)].items() if val(model, l)]
                ins.append(t[0] if t else None)        # None: hidden input
            rec['inputs'] = ins
        else:
            rec['prot'] = val(model, I.prot[s])
            part = [w for w in I.vslots if w != s and (s, w) in I.pt and val(model, I.pt[(s, w)])]
            rec['partner'] = part[0] if part else ('outside' if val(model, I.ptx[s]) else None)
        view.append(rec)
    return view


def sim_summary(I, model):
    out = []
    for sm in I.sims:
        row = {'sim': sm.name, 'legal': val(model, sm.legal), 'trivialised': val(model, sm.triv),
               'vacuous': val(model, sm.vac), 'ok': val(model, sm.ok)}
        row['light'] = sm.light
        if sm.passes and not sm.light:
            last = sm.last
            row['removed'] = [s for s in sm.E if val(model, last.removed[s])]
            row['dominates'] = {str(t): [val(model, a), val(model, b)] for t, (a, b) in sm.dom_lits.items()}
        out.append(row)
    return out


def to_comp(I, view):
    comp = Comp(I.cap)
    ids = {}
    order = sorted(view, key=lambda r: ({'P': 0, 'A': 1, 'Q': 2, 'B': 3}[r['block']], r['slot']))
    for r in order:
        nm = '='.join(r['names']) if r['names'] else None
        n = comp.new_node(r['kind'], 0 if r['block'] == 'P' else 99, name=nm, outdom=(r['out'],))
        n.out = r['out']
        if r['kind'] == 'gate':
            n.gtype = r['type']
            n.typedom = (r['type'],)
            n.bits = list(r['bits']) if r['type'] == 'and' else [0, 0]
            n.prot = False
        else:
            n.prot = r['prot']
            n.protdom = (r['prot'],)
        ids[r['slot']] = n.id
    for r in order:
        if r['kind'] == 'gate':
            for j, v in enumerate(r['inputs']):
                if v is not None:
                    comp.add_edge(ids[v], ids[r['slot']], j)
    for r in order:
        if r['kind'] == 'var' and isinstance(r.get('partner'), int):
            comp.nodes[ids[r['slot']]].partner = ids[r['partner']]
    # distances by BFS from the pattern
    dist = {i: (0 if comp.nodes[i].dist == 0 else None) for i in comp.order}
    frontier = [i for i in comp.order if dist[i] == 0]
    while frontier:
        nxt = []
        for i in frontier:
            n = comp.nodes[i]
            nb = list(n.succ) + [x for x in n.inp if x is not None]
            for m in nb:
                if dist[m] is None:
                    dist[m] = dist[i] + 1
                    nxt.append(m)
        frontier = nxt
    for i in comp.order:
        comp.nodes[i].dist = dist[i] if dist[i] is not None else 99
    slot_of_pid = {pid: s for pid, s in I.pid2slot.items()}
    comp.names = {nm: ids[I.pid2slot[pid]] for nm, pid in I.comp.names.items()}
    comp.no_edge = set((ids[I.pid2slot[a]], ids[I.pid2slot[b]]) for a, b in I.comp.no_edge)
    comp.sum_ge = [(tuple(ids[I.pid2slot[x]] for x in e), k) for e, k in I.comp.sum_ge]
    return comp


def acyclic(comp):
    color = {}

    def dfs(v):
        color[v] = 1
        for w in comp.nodes[v].succ:
            if color.get(w) == 1:
                return False
            if color.get(w) is None and not dfs(w):
                return False
        color[v] = 2
        return True
    return all(color.get(v) is not None or dfs(v) for v in comp.order)


def replay(tree, node, comp, seconds=120.0):
    """Run the WP3.1 engine's analysis on the completion family extending comp."""
    t0 = time.time()
    if not acyclic(comp):
        return {'verdict': 'not-a-violation', 'reason': 'decoded view is cyclic', 'seconds': 0.0}
    pre = ck.node_pre(tree, node)
    res = ck.NodeResult(node)
    stack = [comp]
    first_uncovered = None
    timed_out = False
    while stack:
        if time.time() - t0 > seconds:
            timed_out = True
            break
        cp = stack.pop()
        why = cp.admissible()
        if why is None:
            for cid, tp in pre:
                if ck.match(tp, {}, cp, False) is not None:
                    why = 'pre:' + cid
                    break
        if why is not None:
            res.pruned[why] = res.pruned.get(why, 0) + 1
            continue
        try:
            r = ck.analyse(tree, node, cp, res, True)
        except Need as nd:
            for opt in reversed(nd.options):
                c2 = cp.clone()
                c2.decide(nd.key, opt)
                stack.append(c2)
            continue
        res.completions += 1
        if r[0] == 'vacuous':
            res.vacuous += 1
        elif r[0] == 'discharged':
            key = '%s/%s' % (r[1], r[2])
            res.discharged[key] = res.discharged.get(key, 0) + 1
        elif r[0] == 'covered':
            res.covered[r[1]] = res.covered.get(r[1], 0) + 1
        else:
            res.uncovered_count += 1
            if first_uncovered is None:
                first_uncovered = (cp.describe(), r[1])
            break
    out = {'completions': res.completions, 'pruned': dict(res.pruned), 'vacuous': res.vacuous,
           'discharged': dict(res.discharged), 'covered': dict(res.covered),
           'seconds': round(time.time() - t0, 2)}
    if first_uncovered is not None:
        out['verdict'] = 'violation'
        out['engine_completion'] = first_uncovered[0]
        out['engine_reason'] = str(first_uncovered[1])[:1500]
    elif timed_out:
        out['verdict'] = 'undecided'
    else:
        out['verdict'] = 'not-a-violation'
    return out
