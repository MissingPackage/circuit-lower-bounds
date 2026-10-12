"""Certificate checker for gate-elimination case trees (WP3.1).

Usage:  python -m gecheck.checker CERT_DIR [--log LOG.tsv] [--only ID ...]

A certificate directory holds one JSON file per case-tree node (schema in
gecheck/certificate.schema.json).  For every node the checker enumerates all
completions of the node's full pattern (lazily, see engine.py) and requires:
  * leaf: every completion is discharged by one of the node's actions or an
    ancestor's action (or is vacuous: the output would become constant);
  * internal node: every completion not so discharged matches one of the
    children (exhaustiveness), possibly after a declared pattern automorphism;
  * root: completions matched only by a 'residual' child are listed.
No code path is keyed to a case label: everything case-specific is in the JSON.
"""
import json
import os
import sys
import time
import itertools
from fractions import Fraction as Fr

from .engine import (Comp, Sim, Need, Vacuous, Illegal, is_const, TYPE_BOUNDS,
                     gain_form, dominates, form_str)

ALPHA_STAR = (Fr(1, 43), Fr(6) + Fr(2, 43), Fr(65, 43))   # aT, aI, aQ (FGHK p.15)
COMPLETION_CAP = 10 ** 7
DEG_CAP = int(os.environ.get('GECHECK_DEG_CAP', '3'))
NODE_SECONDS = float(os.environ.get('GECHECK_NODE_SECONDS', '1800'))
STOP_AT_FIRST = os.environ.get('GECHECK_STOP_AT_FIRST', '0') == '1'


def eval_form(f, a=ALPHA_STAR):
    aT, aI, aQ = a
    return f[0] + f[1] * aT + f[2] * aI + f[3] * aQ


# ====================================================================== patterns
class Pattern:
    """A compiled pattern: named nodes with constraints, edges, side conditions."""

    def __init__(self):
        self.nodes = {}      # name -> dict(kind, type set, lo, hi, prot)
        self.edges = []      # (u, v)
        self.distinct = []
        self.no_edge = []
        self.sum_ge = []
        self.partner = []
        self.same = []

    def copy(self):
        p = Pattern()
        p.nodes = {k: dict(v) for k, v in self.nodes.items()}
        p.edges = list(self.edges); p.distinct = list(self.distinct)
        p.no_edge = list(self.no_edge); p.sum_ge = list(self.sum_ge)
        p.partner = list(self.partner); p.same = list(self.same)
        return p

    def extend(self, spec, cap):
        for name, c in spec.get('nodes', {}).items():
            if name in self.nodes:
                cur = self.nodes[name]
                if 'kind' in c and c['kind'] != cur['kind']:
                    raise ValueError('kind conflict for %s' % name)
            else:
                if 'kind' not in c:
                    raise ValueError('new node %s without kind' % name)
                cur = {'kind': c['kind'], 'type': None, 'lo': 0, 'hi': None, 'prot': None}
                self.nodes[name] = cur
            if 'type' in c:
                t = c['type']
                t = set([t]) if isinstance(t, str) else set(t)
                cur['type'] = t if cur['type'] is None else (cur['type'] & t)
            if 'out' in c:
                o = c['out']
                lo, hi = (o, o) if isinstance(o, int) else (o[0], o[1])
                cur['lo'] = max(cur['lo'], lo)
                if hi is not None:
                    cur['hi'] = hi if cur['hi'] is None else min(cur['hi'], hi)
            if 'prot' in c:
                if cur['prot'] is not None and cur['prot'] != c['prot']:
                    raise ValueError('prot conflict for %s' % name)
                cur['prot'] = c['prot']
        for e in spec.get('edges', []):
            if tuple(e) not in self.edges:
                self.edges.append(tuple(e))
        self.distinct += [tuple(e) for e in spec.get('distinct', [])]
        self.no_edge += [tuple(e) for e in spec.get('no_edge', [])]
        self.sum_ge += [(tuple(e[0]), e[1]) for e in spec.get('sum_ge', [])]
        self.partner += [tuple(e) for e in spec.get('partner', [])]
        self.same += [tuple(e) for e in spec.get('same', [])]
        for e in self.edges + self.no_edge + self.distinct + self.partner + self.same:
            for v in e:
                if v not in self.nodes:
                    raise ValueError('unknown node %s in pattern' % v)

    def canon(self):
        """Apply 'same' identifications; returns (pattern, name -> canonical name)."""
        par = {n: n for n in self.nodes}

        def f(a):
            while par[a] != a:
                a = par[a]
            return a
        for a, b in self.same:
            ra, rb = f(a), f(b)
            if ra != rb:
                par[rb] = ra
        canon = {n: f(n) for n in self.nodes}
        p = Pattern()
        for n, c in self.nodes.items():
            r = canon[n]
            if r not in p.nodes:
                p.nodes[r] = dict(c)
            else:
                cur = p.nodes[r]
                if cur['kind'] != c['kind']:
                    raise ValueError('same: kind conflict')
                if c['type'] is not None:
                    cur['type'] = c['type'] if cur['type'] is None else cur['type'] & c['type']
                cur['lo'] = max(cur['lo'], c['lo'])
                if c['hi'] is not None:
                    cur['hi'] = c['hi'] if cur['hi'] is None else min(cur['hi'], c['hi'])
                if c['prot'] is not None:
                    if cur['prot'] is not None and cur['prot'] != c['prot']:
                        raise ValueError('same: prot conflict')
                    cur['prot'] = c['prot']
        m = lambda e: tuple(canon[v] for v in e)
        p.edges = [m(e) for e in self.edges]
        p.distinct = [m(e) for e in self.distinct]
        p.no_edge = [m(e) for e in self.no_edge]
        p.sum_ge = [(m(e), k) for e, k in self.sum_ge]
        p.partner = [m(e) for e in self.partner]
        return p, canon


# ====================================================================== matcher
class _Unknown(Exception):
    pass


def _fact(comp, ask, fn, *args):
    if ask:
        return getattr(comp, fn)(*args)
    n = comp.nodes[args[0]]
    if fn == 'ask_type':
        if n.gtype is None:
            raise _Unknown()
        return n.gtype
    if fn == 'ask_out':
        if n.out is None:
            raise _Unknown()
        return n.out
    if fn == 'ask_prot':
        if n.prot is None:
            raise _Unknown()
        return n.prot
    if fn == 'ask_partner':
        if n.partner is None:
            raise _Unknown()
        return n.partner
    if fn == 'ask_all_succ':
        if n.out is None or len(n.succ) < n.out:
            raise _Unknown()
        return n.succ
    if fn == 'ask_inp':
        v = n.inp[args[1]]
        if v is None:
            raise _Unknown()
        return v
    raise ValueError(fn)


def _edge(comp, ask, u, v):
    vn = comp.nodes[v]
    if vn.kind != 'gate':
        return False
    if u in vn.inp:
        return True
    for k in (0, 1):
        if vn.inp[k] is None:
            _fact(comp, ask, 'ask_inp', v, k)
    return u in vn.inp


def _node_ok(pat, name, nid, comp, ask):
    c = pat.nodes[name]
    n = comp.nodes[nid]
    if n.kind != c['kind']:
        return False
    if c['type'] is not None:
        if _fact(comp, ask, 'ask_type', nid) not in c['type']:
            return False
    if c['lo'] > 0 or c['hi'] is not None:
        o = _fact(comp, ask, 'ask_out', nid)
        if o < c['lo'] or (c['hi'] is not None and o > c['hi']):
            return False
    if c['prot'] is not None:
        if _fact(comp, ask, 'ask_prot', nid) != c['prot']:
            return False
    return True


def _check_partial(pat, M, comp, ask, newname):
    """Check all side conditions whose names are mapped and involve newname."""
    for u, v in pat.edges:
        if newname in (u, v) and u in M and v in M:
            if not _edge(comp, ask, M[u], M[v]):
                return False
    for u, v in pat.no_edge:
        if newname in (u, v) and u in M and v in M:
            if comp.nodes[M[v]].kind == 'gate' and _edge(comp, ask, M[u], M[v]):
                return False
    for u, v in pat.distinct:
        if newname in (u, v) and u in M and v in M and M[u] == M[v]:
            return False
    for u, v in pat.partner:
        if newname in (u, v) and u in M and v in M:
            if not _fact(comp, ask, 'ask_prot', M[u]):
                return False
            if _fact(comp, ask, 'ask_partner', M[u]) != M[v]:
                return False
    for names, k in pat.sum_ge:
        if newname in names and all(x in M for x in names):
            if sum(_fact(comp, ask, 'ask_out', M[x]) for x in names) < k:
                return False
    return True


def _candidates(pat, name, M, comp, ask):
    for u, v in pat.edges:
        if v == name and u in M:
            if comp.nodes[M[u]].kind is None:
                continue
            return list(dict.fromkeys(_fact(comp, ask, 'ask_all_succ', M[u])))
    for u, v in pat.edges:
        if u == name and v in M:
            out = []
            for k in (0, 1):
                w = _fact(comp, ask, 'ask_inp', M[v], k)
                if not is_const(w) and w not in out:
                    out.append(w)
            return out
    for u, v in pat.partner:
        other = v if u == name else (u if v == name else None)
        if other is not None and other in M:
            if not _fact(comp, ask, 'ask_prot', M[other]):
                return []
            return [_fact(comp, ask, 'ask_partner', M[other])]
    return list(comp.order)


def _order(pat, fixed):
    order = []
    have = set(fixed)
    rest = [n for n in pat.nodes if n not in have]
    while rest:
        pick = None
        for n in rest:
            if any((u in have and v == n) or (v in have and u == n) for u, v in pat.edges + pat.partner):
                pick = n
                break
        if pick is None:
            pick = rest[0]
        order.append(pick)
        have.add(pick)
        rest.remove(pick)
    return order


def match(pat, fixed, comp, ask):
    """Find a mapping of pattern names to completion nodes extending `fixed`.
    ask=True: unknown facts raise Need (the driver branches); ask=False: unknown
    facts make a candidate fail (used for forbidden triggers)."""
    M = dict(fixed)
    try:
        for name in fixed:
            if not _node_ok(pat, name, M[name], comp, ask):
                return None
        tmp = {}
        for name in fixed:
            tmp[name] = M[name]
            if not _check_partial(pat, tmp, comp, ask, name):
                return None
    except _Unknown:
        return None
    order = _order(pat, fixed)

    def rec(i):
        if i == len(order):
            return True
        name = order[i]
        try:
            cands = _candidates(pat, name, M, comp, ask)
        except _Unknown:
            return False
        for nid in cands:
            try:
                if not _node_ok(pat, name, nid, comp, ask):
                    continue
                M[name] = nid
                if not _check_partial(pat, M, comp, ask, name):
                    del M[name]
                    continue
            except _Unknown:
                M.pop(name, None)
                continue
            if rec(i + 1):
                return True
            del M[name]
        return False
    return dict(M) if rec(0) else None


# ====================================================================== case tree
class CaseNode:
    def __init__(self, spec, path):
        self.spec = spec
        self.path = path
        self.id = spec['id']
        self.label = spec.get('label', self.id)
        self.kind = spec['kind']            # leaf | internal | union | residual | root
        self.parent_id = spec.get('parent')
        self.inherit = spec.get('inherit', True)
        self.children_ids = spec.get('children', [])
        self.actions = spec.get('actions', [])
        self.symmetries = spec.get('symmetries', [])
        self.R = spec.get('radius', 1)
        self.cap = spec.get('deg_cap', DEG_CAP)
        self.paper_leaf = spec.get('paper_leaf', False)
        self.pre_ids = spec.get('pre', [])
        self.parent = None
        self.children = []
        self.full = None
        self.canon = None
        self.raw = None

    def ancestors(self):
        a = []
        p = self.parent
        while p is not None:
            a.append(p)
            p = p.parent
        return a


REQUIRED = {'id', 'kind'}
KINDS = {'leaf', 'internal', 'union', 'residual', 'root'}
STEP_KINDS = {'const', 'affine', 'quadratic'}


def validate_spec(spec, fname):
    missing = REQUIRED - set(spec)
    if missing:
        raise ValueError('%s: missing keys %s' % (fname, sorted(missing)))
    if spec['kind'] not in KINDS:
        raise ValueError('%s: bad kind %s' % (fname, spec['kind']))
    for a in spec.get('actions', []):
        if not a.get('steps') or not a.get('types'):
            raise ValueError('%s: action without steps or types' % fname)
        for t in a['types']:
            if t not in TYPE_BOUNDS:
                raise ValueError('%s: unknown type %s' % (fname, t))
        for s in a['steps']:
            if s.get('kind') not in STEP_KINDS:
                raise ValueError('%s: bad step kind %s' % (fname, s.get('kind')))
            if s['kind'] != 'const' and 'src' not in s:
                raise ValueError('%s: %s step without src' % (fname, s['kind']))


def load_tree(cert_dir):
    nodes = {}
    for fn in sorted(os.listdir(cert_dir)):
        if not fn.endswith('.json'):
            continue
        with open(os.path.join(cert_dir, fn)) as f:
            spec = json.load(f)
        validate_spec(spec, fn)
        if spec['id'] in nodes:
            raise ValueError('duplicate id %s' % spec['id'])
        nodes[spec['id']] = CaseNode(spec, fn)
    for n in nodes.values():
        if n.parent_id is not None:
            if n.parent_id not in nodes:
                raise ValueError('%s: unknown parent %s' % (n.id, n.parent_id))
            n.parent = nodes[n.parent_id]
        for c in n.children_ids:
            if c not in nodes:
                raise ValueError('%s: unknown child %s (missing certificate)' % (n.id, c))
            if nodes[c].parent_id != n.id:
                raise ValueError('%s: child %s declares parent %s' % (n.id, c, nodes[c].parent_id))
            n.children.append(nodes[c])
    # full patterns
    def build(n):
        if n.full is not None:
            return
        if n.parent is not None and n.inherit:
            build(n.parent)
            p = n.parent.raw.copy()
        else:
            p = Pattern()
        p.extend(n.spec.get('pattern', {}), n.cap)
        n.raw = p
        n.full, n.canon = p.canon()
    for n in nodes.values():
        build(n)
    for n in nodes.values():
        for sg in n.symmetries:
            check_automorphism(n, sg)
    return nodes


class CertificateError(ValueError):
    pass


def check_automorphism(n, sg):
    """A declared symmetry must map the node's full pattern onto itself."""
    p = n.full
    f = lambda v: sg.get(v, v)
    for k, v in sg.items():
        if k not in p.nodes or v not in p.nodes:
            raise CertificateError('%s: symmetry names unknown node %s/%s' % (n.id, k, v))
    if sorted(f(v) for v in p.nodes) != sorted(p.nodes):
        raise CertificateError('%s: declared symmetry %s is not a bijection' % (n.id, sg))
    for v, c in p.nodes.items():
        if c != p.nodes[f(v)]:
            raise CertificateError('%s: declared symmetry %s is not an automorphism (node %s)' % (n.id, sg, v))
    for name in ('edges', 'distinct', 'no_edge', 'partner'):
        a = sorted(tuple(f(v) for v in e) for e in getattr(p, name))
        b = sorted(tuple(e) for e in getattr(p, name))
        if name in ('distinct', 'partner'):
            a = sorted(tuple(sorted(e)) for e in a)
            b = sorted(tuple(sorted(e)) for e in b)
        if a != b:
            raise CertificateError('%s: declared symmetry %s is not an automorphism (%s)' % (n.id, sg, name))


def trigger_patterns(nodes, cid):
    n = nodes[cid]
    if n.kind == 'union':
        out = []
        for c in n.children:
            out += trigger_patterns(nodes, c.id)
        return out
    return [(cid, n.full)]


def node_pre(nodes, n):
    ids = []
    m = n
    while m is not None:
        ids = m.pre_ids + ids
        m = m.parent if m.inherit else None
    pats = []
    for cid in ids:
        pats += trigger_patterns(nodes, cid)
    return pats


# ====================================================================== completions
def initial_comps(n):
    """All identifications of pattern nodes (respecting kinds and 'distinct'),
    each built as a base completion."""
    pat = n.full
    names = list(pat.nodes)
    distinct = set(pat.distinct) | set((b, a) for a, b in pat.distinct)
    blocks_list = []

    def rec(i, blocks):
        if i == len(names):
            blocks_list.append([list(b) for b in blocks])
            return
        nm = names[i]
        for b in blocks:
            if pat.nodes[b[0]]['kind'] != pat.nodes[nm]['kind']:
                continue
            if any((x, nm) in distinct for x in b):
                continue
            b.append(nm)
            rec(i + 1, blocks)
            b.pop()
        blocks.append([nm])
        rec(i + 1, blocks)
        blocks.pop()
    rec(0, [])
    comps = []
    for blocks in blocks_list:
        c = build_comp(n, blocks)
        if c is not None:
            comps.append(c)
    return comps


def build_comp(n, blocks):
    pat = n.full
    cap = n.cap
    comp = Comp(cap)
    names = {}
    for b in blocks:
        kind = pat.nodes[b[0]]['kind']
        lo, hi, types, prot = 0, cap, None, None
        for nm in b:
            c = pat.nodes[nm]
            lo = max(lo, c['lo'])
            if c['hi'] is not None:
                hi = min(hi, c['hi'])
            if c['type'] is not None:
                types = c['type'] if types is None else types & c['type']
            if c['prot'] is not None:
                if prot is not None and prot != c['prot']:
                    return None
                prot = c['prot']
        if lo > hi or (types is not None and not types):
            return None
        node = comp.new_node(kind, 0, name='=' .join(b), outdom=tuple(range(lo, hi + 1)))
        if types is not None:
            node.typedom = tuple(sorted(types))
            if len(types) == 1:
                node.gtype = next(iter(types))
        if kind == 'var' and prot is not None:
            node.prot = prot
            node.protdom = (prot,)
        if kind == 'gate':
            node.prot = False
        for nm in b:
            names[nm] = node.id
    for u, v in pat.edges:
        a, b = names[u], names[v]
        if a == b:
            return None
        vn = comp.nodes[b]
        if vn.kind != 'gate':
            return None
        if a in vn.inp:
            return None          # the same input twice: not normalized (Transformation 5)
        if None not in vn.inp:
            return None
        if comp.reaches(b, a):
            return None
        comp.add_edge(a, b)
    for u, v in pat.no_edge:
        comp.no_edge = set(comp.no_edge) | {(names[u], names[v])}
    for u, v in pat.partner:
        a, b = names[u], names[v]
        if a == b:
            return None
        for x, y in ((a, b), (b, a)):
            xn = comp.nodes[x]
            if xn.prot is False or (xn.partner is not None and xn.partner != y):
                return None
            xn.prot = True
            xn.partner = y
    for u, v in pat.no_edge:
        if names[u] in comp.nodes[names[v]].inp:
            return None
    comp.sum_ge = [(tuple(names[x] for x in e), k) for e, k in pat.sum_ge]
    for nid in comp.order:
        nd = comp.nodes[nid]
        if len(nd.succ) > max(nd.outdom):
            return None
    comp.names = {nm: names[n.canon[nm]] if nm in n.canon else names[nm] for nm in n.canon}
    return comp


# ====================================================================== actions
def run_action(comp, act, names, R, suggestions):
    """Frugal evaluation of one action on one completion.
    Returns ('ok', type, form, m) | ('vacuous',) | ('fail', reasons); facts whose
    absence blocked a transformation or a measure are appended to `suggestions`."""
    steps = act['steps']
    choices = []
    for s in steps:
        v = s.get('value', 0)
        choices.append([0, 1] if isinstance(v, dict) else [v])
    reasons = []
    best = None
    for combo in itertools.product(*choices):
        sim = Sim(comp, R, True)
        substituted = []
        ok = True
        try:
            for s, val in zip(steps, combo):
                if s['var'] not in names:
                    raise Illegal('unknown node %s' % s['var'])
                x = names[s['var']]
                src = names.get(s.get('src')) if s.get('src') else None
                if s.get('src') and src is None:
                    raise Illegal('unknown source %s' % s['src'])
                sim.subst(x, s['kind'], val, src)
                substituted.append(x)
                sim.normalize()
                v = s.get('value', 0)
                if isinstance(v, dict) and 'trivialize' in v:
                    tgt = names.get(v['trivialize'])
                    if tgt is None or tgt not in sim.const_removed:
                        ok = False
                        reasons.append('%s=%d does not trivialise %s' % (s['var'], val, v['trivialize']))
                        break
        except Vacuous:
            return ('vacuous',)
        except Need as nd:
            suggestions.append((1, nd))       # a fact needed by the substitution itself
            continue
        except Illegal as e:
            reasons.append('illegal: %s' % e)
            continue
        finally:
            suggestions.extend((0, nd) for nd in sim.suggest)
            for o in sim.anon_effects:
                try:
                    comp.ask_all_succ(o)
                except Need as nd:
                    suggestions.append((3, nd))
                    break
        if not ok:
            continue
        passed = False
        m = None
        modes = ('conservative',) if sim.suggest else ('conservative', 'exact')
        try:
            for mode in modes:
                if mode == 'conservative':
                    m = sim.measure_conservative(substituted, sim.subst_troubled)
                else:
                    m = sim.measure(substituted)
                form = gain_form(m)
                for t in act['types']:
                    if dominates(form, TYPE_BOUNDS[t]):
                        cand = ('ok', t, form, m)
                        if best is None or eval_form(form) < eval_form(best[2]):
                            best = cand
                        passed = True
                        break
                if passed:
                    break
        except Need as nd:
            suggestions.append((2, nd))
            continue
        if not passed:
            n_old = len([1 for p_, _ in suggestions if p_ == 0])
            suggestions.extend((0, nd) for nd in sim.suggest[n_old:])
            reasons.append('gain %s (g=%d t=%d i=%d q=%d pending=%d) below types %s' % (
                form_str(form), m['g'], m['t'], m['i'], m['q'], m['pending'], act['types']))
    if best is not None:
        return best
    return ('fail', reasons)


# ====================================================================== driver
class NodeResult:
    def __init__(self, n):
        self.node = n
        self.completions = 0
        self.pruned = {}
        self.vacuous = 0
        self.discharged = {}
        self.types = {}
        self.min_slack = None
        self.min_form = None
        self.covered = {}
        self.residual = []
        self.uncovered = []
        self.uncovered_count = 0
        self.fail_reasons = {}
        self.capped = False
        self.timed_out = False
        self.seconds = 0.0
        self.error = None


def analyse(nodes, n, comp, res, own_actions):
    # 1. actions of the node and of its ancestors
    owners = [n] + [a for a in n.ancestors() if True]
    chain = [n]
    m = n
    while m.parent is not None and m.inherit:
        m = m.parent
        chain.append(m)
    last_fail = None
    suggestions = []
    for owner in chain:
        for act in owner.actions:
            r = run_action(comp, act, comp.names, n.R, suggestions)
            if r[0] == 'vacuous':
                return ('vacuous', owner.id)
            if r[0] == 'ok':
                return ('discharged', owner.id, act.get('name', '?'), r[1], r[2])
            if owner is n:
                last_fail = (act.get('name', '?'), r[1])
    if suggestions:
        # refine the completion on the first blocking fact, normalization blocks first
        raise min(suggestions, key=lambda p: p[0])[1]
    # 2. children (exhaustiveness)
    sigmas = [{}] + n.symmetries
    for c in n.children:
        members = c.children if c.kind == 'union' else [c]
        for mem in members:
            shared = [nm for nm in mem.full.nodes if nm in comp.names] if mem.inherit else \
                     [nm for nm in mem.full.nodes if nm in comp.names]
            for sg in sigmas:
                fixed = {}
                bad = False
                for nm in shared:
                    src = sg.get(nm, nm)
                    if src not in comp.names:
                        bad = True
                        break
                    fixed[nm] = comp.names[src]
                if bad:
                    continue
                mm = match(mem.full, fixed, comp, True)
                if mm is not None:
                    return ('covered', c.id)
    return ('uncovered', last_fail)


def check_node(nodes, n, log=print):
    res = NodeResult(n)
    t0 = time.time()
    pre = node_pre(nodes, n)
    stack = initial_comps(n)
    if not stack:
        res.error = 'pattern admits no completion'
    deadline = t0 + NODE_SECONDS
    while stack:
        if time.time() > deadline:
            res.timed_out = True
            break
        comp = stack.pop()
        why = comp.admissible()
        if why is None:
            for cid, tp in pre:
                if match(tp, {}, comp, False) is not None:
                    why = 'pre:' + cid
                    break
        if why is not None:
            res.pruned[why] = res.pruned.get(why, 0) + 1
            continue
        try:
            r = analyse(nodes, n, comp, res, True)
        except Need as nd:
            for opt in reversed(nd.options):      # explore options in listed order
                c2 = comp.clone()
                c2.decide(nd.key, opt)
                stack.append(c2)
            continue
        res.completions += 1
        if res.completions > COMPLETION_CAP:
            res.capped = True
            break
        if r[0] == 'vacuous':
            res.vacuous += 1
        elif r[0] == 'discharged':
            key = '%s/%s' % (r[1], r[2])
            res.discharged[key] = res.discharged.get(key, 0) + 1
            if r[1] == n.id:
                res.types[r[3]] = res.types.get(r[3], 0) + 1
                slack = eval_form(r[4]) - eval_form(TYPE_BOUNDS[r[3]])
                if res.min_slack is None or slack < res.min_slack:
                    res.min_slack = slack
                    res.min_form = r[4]
        elif r[0] == 'covered':
            if nodes[r[1]].kind == 'residual':
                if len(res.residual) < 50:
                    res.residual.append(comp.describe())
            res.covered[r[1]] = res.covered.get(r[1], 0) + 1
        else:
            res.uncovered_count += 1
            if len(res.uncovered) < 5:
                res.uncovered.append((comp.describe(), r[1]))
            if STOP_AT_FIRST:
                break
    res.seconds = time.time() - t0
    return res


def status_of(res):
    n = res.node
    if res.error:
        return 'rejected', res.error
    if res.uncovered_count:
        d, f = res.uncovered[0]
        why = 'uncovered completion' if n.kind != 'leaf' else 'completion not discharged'
        extra = ''
        if f:
            extra = ' [own action %s failed: %s]' % (f[0], '; '.join(f[1][:3]))
        return 'rejected', '%s (%d of %d): %s%s' % (why, res.uncovered_count, res.completions, d, extra)
    if res.capped:
        return 'not-checked-at-this-radius', 'completion cap %d exceeded' % COMPLETION_CAP
    if res.timed_out:
        return 'not-checked (time budget)', 'stopped after %.0f s with %d completions, 0 uncovered so far' % (
            res.seconds, res.completions)
    if n.kind == 'leaf' and n.actions and not res.types and res.completions:
        return 'verified', 'all completions discharged by ancestors or vacuous'
    return 'verified', ''


def _row(nodes, n, res):
    st, why = status_of(res)
    gain = ''
    if res.types:
        ts = sorted(res.types)
        gain = 'types ' + ','.join('%d(x%d)' % (t, res.types[t]) for t in ts)
        gain += '; weakest completion %s, slack at alpha* %s' % (form_str(res.min_form), res.min_slack)
    return {
        'id': n.id, 'label': n.label, 'kind': n.kind, 'paper_leaf': n.paper_leaf,
        'status': st, 'reason': why, 'completions': res.completions,
        'pruned': sum(res.pruned.values()), 'vacuous': res.vacuous,
        'discharged': dict(res.discharged), 'covered': dict(res.covered),
        'certified_types': sorted(res.types), 'certified_gain': gain,
        'claimed_types': sorted(set(t for a in n.actions for t in a['types'])),
        'exhaustive': (res.uncovered_count == 0 and not res.capped and not res.error and not res.timed_out)
        if n.kind in ('internal', 'root') else None,
        'uncovered_count': res.uncovered_count,
        'uncovered_examples': [d for d, _ in res.uncovered],
        'residual_count': res.covered.get('R67', 0),
        'residual_examples': res.residual, 'seconds': round(res.seconds, 1),
        'deg_cap': n.cap, 'radius': n.R, 'node_seconds': NODE_SECONDS,
    }


def _work(args):
    cert_dir, nid = args
    nodes = load_tree(cert_dir)
    n = nodes[nid]
    res = check_node(nodes, n)
    return _row(nodes, n, res)


def run_tree(cert_dir, logpath=None, only=None, quiet=False, jobs=1):
    nodes = load_tree(cert_dir)
    order = sorted(nodes.values(), key=lambda n: (n.id.count('.'), n.id))
    ids = [n.id for n in order if (not only or n.id in only) and n.kind not in ('union', 'residual')]
    if jobs > 1:
        import multiprocessing as mp
        with mp.Pool(jobs) as pool:
            rows = pool.map(_work, [(cert_dir, i) for i in ids], chunksize=1)
    else:
        rows = [_work((cert_dir, i)) for i in ids]
    for row in rows:
        if not quiet:
            print('%-12s %-9s %-26s compl=%-7d pruned=%-7d vac=%-5d %6.1fs %s %s' % (
                row['id'], row['kind'], row['status'], row['completions'], row['pruned'], row['vacuous'],
                row['seconds'], row['certified_gain'], ('| ' + row['reason'][:600]) if row['reason'] else ''),
                flush=True)
            if row['covered']:
                print('    covered by children: %s' % row['covered'], flush=True)
            if row['discharged']:
                print('    discharged by: %s' % row['discharged'], flush=True)
    if logpath:
        with open(logpath, 'w') as f:
            json.dump(rows, f, indent=1, default=str)
    return rows


def main(argv):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('cert_dir')
    ap.add_argument('--log')
    ap.add_argument('--only', nargs='*')
    ap.add_argument('--jobs', type=int, default=1)
    a = ap.parse_args(argv)
    run_tree(a.cert_dir, a.log, a.only, jobs=a.jobs)


if __name__ == '__main__':
    main(sys.argv[1:])
