"""Lazy completion engine for gate-elimination case certificates (WP3.1).

Model (FGHK rev. 2, Sections 2.1, 3.2, 3.4; see wp3/wp31_preregistration_2026-10-12.txt):
  * variables (in-degree 0) and gates (in-degree 2, and-type or xor-type);
  * every gate's output negation is normalised to 0 (a global re-labelling that
    preserves types, degrees and troubled gates), so an and-gate is
    (s0 + b0)(s1 + b1) and an xor-gate is s0 + s1; b_k is the value of input k
    that trivialises the and-gate;
  * a completion is built lazily: any unknown fact (gate type, polarity bit,
    out-degree, identity of an unknown neighbour, protected flag, quadratic
    partner) raises Need(key, options) and the driver branches on it.

No code in this module is keyed to a case label.
"""
from fractions import Fraction as Fr

CONST = 'C'


class Need(Exception):
    def __init__(self, key, options):
        super().__init__(key)
        self.key = key
        self.options = options


class Vacuous(Exception):
    """The output gate would become constant: impossible for an rdq-disperser
    with s >= d + 2 (FGHK p.22); such a completion cannot occur."""


class Illegal(Exception):
    """A substitution violates its legality condition (Lemma 3.1.1 / Prop. 3.4.2)."""


class Node:
    __slots__ = ('id', 'kind', 'gtype', 'bits', 'inp', 'out', 'outdom', 'succ',
                 'prot', 'partner', 'dist', 'name', 'typedom', 'protdom',
                 # simulation-only fields
                 'flip', 'tt', 'removed', 'output', 'bout', 'anon', 'mout')

    def __init__(self, nid, kind, dist=0, name=None):
        self.id = nid
        self.kind = kind
        self.gtype = None
        self.bits = [None, None]
        self.inp = [None, None] if kind == 'gate' else []
        self.out = None
        self.outdom = None
        self.succ = []
        self.prot = None if kind == 'var' else False
        self.partner = None
        self.dist = dist
        self.name = name
        self.typedom = ('and', 'xor')
        self.protdom = (False, True)
        self.flip = [0, 0, 0]
        self.tt = None
        self.removed = False
        self.output = False
        self.bout = None
        self.anon = []
        self.mout = []

    def clone(self):
        n = Node.__new__(Node)
        n.id = self.id; n.kind = self.kind; n.gtype = self.gtype
        n.bits = list(self.bits); n.inp = list(self.inp); n.out = self.out
        n.outdom = self.outdom; n.succ = list(self.succ); n.prot = self.prot
        n.partner = self.partner; n.dist = self.dist; n.name = self.name
        n.typedom = self.typedom; n.protdom = self.protdom
        n.flip = list(self.flip); n.tt = self.tt; n.removed = self.removed
        n.output = self.output; n.bout = self.bout; n.anon = list(self.anon)
        n.mout = list(self.mout)
        return n


def is_const(v):
    return isinstance(v, tuple) and v[0] == CONST


class Comp:
    """A (partial) completion of a pattern: the base facts about the original circuit."""

    def __init__(self, cap):
        self.nodes = {}
        self.order = []
        self.cap = cap
        self.no_edge = set()
        self.sum_ge = []      # (node ids, k): sum of out-degrees >= k
        self.names = {}       # pattern name -> node id
        self.ndec = 0

    def clone(self):
        c = Comp.__new__(Comp)
        c.nodes = {k: v.clone() for k, v in self.nodes.items()}
        c.order = list(self.order)
        c.cap = self.cap
        c.no_edge = self.no_edge
        c.sum_ge = self.sum_ge
        c.names = self.names
        c.ndec = self.ndec
        return c

    # ------------------------------------------------------------ construction
    def new_node(self, kind, dist, name=None, outdom=None):
        nid = 'n%d' % len(self.order)
        n = Node(nid, kind, dist, name)
        if outdom is None:
            outdom = tuple(range(1, self.cap + 1))
        n.outdom = tuple(outdom)
        self.nodes[nid] = n
        self.order.append(nid)
        return n

    def add_edge(self, u, g, slot=None):
        gn = self.nodes[g]
        if slot is None:
            slot = gn.inp.index(None)
        assert gn.inp[slot] is None
        gn.inp[slot] = u
        un = self.nodes[u]
        un.succ.append(g)
        gn.dist = min(gn.dist, un.dist + 1)
        un.dist = min(un.dist, gn.dist + 1)

    # ------------------------------------------------------------ queries
    def reaches(self, a, b):
        """True if b is reachable from a by known edges."""
        seen = set()
        st = [a]
        while st:
            v = st.pop()
            if v == b:
                return True
            if v in seen:
                continue
            seen.add(v)
            st.extend(self.nodes[v].succ)
        return False

    def free_out(self, m):
        n = self.nodes[m]
        if n.out is not None:
            return n.out > len(n.succ)
        return max(n.outdom) > len(n.succ)

    def opts_succ(self, n):
        opts = []
        for g in self.order:
            gn = self.nodes[g]
            if gn.kind != 'gate' or g == n or None not in gn.inp:
                continue
            if n in gn.inp:
                continue  # identical inputs: not normalized
            if (n, g) in self.no_edge or self.reaches(g, n):
                continue
            opts.append(g)
        opts.append(('newgate',))
        return opts

    def opts_inp(self, g, k):
        gn = self.nodes[g]
        other = gn.inp[1 - k]
        opts = []
        for m in self.order:
            if m == g or m == other or not self.free_out(m):
                continue
            if (m, g) in self.no_edge or self.reaches(g, m):
                continue
            opts.append(m)
        opts.append(('newvar',))
        opts.append(('newgate',))
        return opts

    def opts_partner(self, v):
        opts = []
        for m in self.order:
            mn = self.nodes[m]
            if m == v or mn.kind != 'var' or mn.partner is not None or mn.prot is False:
                continue
            opts.append(m)
        opts.append(('newvar',))
        return opts

    def ask_type(self, g):
        n = self.nodes[g]
        if n.gtype is None:
            raise Need(('type', g), list(n.typedom))
        return n.gtype

    def ask_bit(self, g, i):
        n = self.nodes[g]
        if n.bits[i] is None:
            raise Need(('bit', g, i), [0, 1])
        return n.bits[i]

    def ask_out(self, v):
        n = self.nodes[v]
        if n.out is None:
            opts = [d for d in n.outdom if d >= len(n.succ)]
            raise Need(('out', v), opts)
        return n.out

    def ask_is_zero(self, v):
        n = self.nodes[v]
        if n.out is not None:
            return n.out == 0
        if n.succ or 0 not in n.outdom:
            return False
        if n.outdom == (0,):
            return True
        raise Need(('outz', v), [True, False])

    def ask_all_succ(self, v):
        n = self.nodes[v]
        o = self.ask_out(v)
        if len(n.succ) < o:
            raise Need(('succ', v), self.opts_succ(v))
        return n.succ

    def ask_inp(self, g, k):
        n = self.nodes[g]
        if n.inp[k] is None:
            raise Need(('inp', g, k), self.opts_inp(g, k))
        return n.inp[k]

    def ask_prot(self, v):
        n = self.nodes[v]
        if n.prot is None:
            raise Need(('prot', v), list(n.protdom))
        return n.prot

    def ask_partner(self, v):
        n = self.nodes[v]
        if n.partner is None:
            raise Need(('partner', v), self.opts_partner(v))
        return n.partner

    # ------------------------------------------------------------ decisions
    def decide(self, key, val):
        self.ndec += 1
        kind = key[0]
        if kind == 'type':
            self.nodes[key[1]].gtype = val
        elif kind == 'bit':
            self.nodes[key[1]].bits[key[2]] = val
        elif kind == 'out':
            self.nodes[key[1]].out = val
        elif kind == 'outz':
            n = self.nodes[key[1]]
            if val:
                n.out = 0
            else:
                n.outdom = tuple(d for d in n.outdom if d != 0)
        elif kind == 'prot':
            self.nodes[key[1]].prot = val
        elif kind == 'partner':
            v = key[1]
            vn = self.nodes[v]
            if isinstance(val, tuple):
                w = self.new_node('var', vn.dist + 1, outdom=tuple(range(0, self.cap + 1)))
                w = w.id
            else:
                w = val
            self.nodes[w].prot = True
            self.nodes[w].partner = v
            vn.partner = w
        elif kind == 'succ':
            v = key[1]
            if isinstance(val, tuple):
                g = self.new_node('gate', self.nodes[v].dist + 1,
                                  outdom=tuple(range(0, self.cap + 1)))
                self.add_edge(v, g.id, 0)
            else:
                self.add_edge(v, val)
        elif kind == 'inp':
            g, k = key[1], key[2]
            if isinstance(val, tuple):
                knd = 'var' if val[0] == 'newvar' else 'gate'
                m = self.new_node(knd, self.nodes[g].dist + 1)
                self.add_edge(m.id, g, k)
            else:
                self.add_edge(val, g, k)
        else:
            raise ValueError(key)

    # ------------------------------------------------------------ admissibility
    def admissible(self):
        """Known-fact checks: degrees, normalization (FGHK Transformations 1, 4, 5),
        a single output, quadratic partners. Returns None or a reason string."""
        outputs = 0
        for nid in self.order:
            n = self.nodes[nid]
            if n.out is not None:
                if len(n.succ) > n.out:
                    return 'degree'
                if n.kind == 'gate' and n.out == 0:
                    outputs += 1
            elif len(n.succ) > max(n.outdom):
                return 'degree'
            if n.kind == 'gate':
                a, b = n.inp
                if a is not None and a == b:
                    return 'N5'
                # Transformation 4 (useless gate)
                if n.out == 1 and len(n.succ) == 1 and a is not None and b is not None:
                    q = self.nodes[n.succ[0]]
                    if q.id != nid and (a in q.inp or b in q.inp):
                        return 'N4'
            else:
                if n.prot is False and n.partner is not None:
                    return 'partner'
                if n.out == 0 and n.prot is False and n.partner is None:
                    pass
        if outputs > 1:
            return 'outputs'
        for ids, k in self.sum_ge:
            tot = 0
            for v in ids:
                n = self.nodes[v]
                tot += n.out if n.out is not None else max(n.outdom)
            if tot < k:
                return 'sum_ge'
        return None

    def describe(self):
        parts = []
        for nid in self.order:
            n = self.nodes[nid]
            nm = n.name or nid
            if n.kind == 'var':
                s = '%s:var out=%s prot=%s' % (nm, n.out, n.prot)
                if n.partner:
                    s += ' partner=%s' % (self.nodes[n.partner].name or n.partner)
            else:
                ins = [(self.nodes[i].name or i) if i is not None else '?' for i in n.inp]
                s = '%s:%s(%s) out=%s bits=%s' % (nm, n.gtype or '?', ','.join(ins), n.out,
                                                  ''.join('?' if b is None else str(b) for b in n.bits))
            parts.append(s)
        return '; '.join(parts)


# ====================================================================== simulation
class Sim:
    """Working copy: substitutions and FGHK normalization (Transformations 1-5 in
    order) applied to gates within radius R of the pattern.

    Out-degrees in the working copy are base out-degree + delta (field dout); the
    base value is asked only when a decision depends on it.  Unknown successor
    slots of a removed passing gate are transferred anonymously (field anon) and
    revealed only if exact troubled-gate accounting needs them.  Transformations
    1 and 4 are applied only when decidable from known facts; skipping an
    applicable transformation is sound because normalization never increases
    mu (FGHK Lemma 3.5.1)."""

    def __init__(self, base, R, frugal=False):
        self.base = base
        self.R = R
        self.frugal = frugal
        self.blocked = set()
        self.suggest = []
        self.anon_effects = []     # origins whose unrevealed successors were affected
        self.nodes = {k: v.clone() for k, v in base.nodes.items()}
        for n in self.nodes.values():
            n.bout = 0          # used as the out-degree delta
        self.removed = []
        self.const_removed = set()
        self.touched = set()
        self.q_dec = 0
        self.subst_troubled = 0
        self.dirty = set()
        self.rank = {nid: i for i, nid in enumerate(base.order)}
        self.events = []

    # ---- degrees
    def block(self, o):
        """Number of still-unrevealed base successor slots of origin o."""
        return self.base.ask_out(o) - len(self.base.nodes[o].succ)

    def out(self, v):
        n = self.nodes[v]
        return self.base.ask_out(v) + n.bout + sum(self.block(o) for o in n.anon)

    def out_known(self, v):
        n = self.nodes[v]
        b = self.base.nodes[v].out
        if b is None:
            return None
        tot = b + n.bout
        for o in n.anon:
            bo = self.base.nodes[o].out
            if bo is None:
                return None
            tot += bo - len(self.base.nodes[o].succ)
        return tot

    def has_succ(self, v):
        n = self.nodes[v]
        return bool(n.succ) or bool(n.anon)

    # ---- delegated asks (unknown facts are unmodified base facts)
    def all_succ(self, v):
        self.base.ask_all_succ(v)
        for o in list(dict.fromkeys(self.nodes[v].anon)):
            self.base.ask_all_succ(o)
        n = self.nodes[v]
        assert all(self.block(o) == 0 for o in n.anon)
        n.anon = []
        return n.succ

    def unknown_slots(self, v):
        b = self.base.nodes[v]
        return self.base.ask_out(v) - len(b.succ)

    def inp(self, g, k):
        n = self.nodes[g]
        if n.inp[k] is None:
            self.base.ask_inp(g, k)
        return n.inp[k]

    def gtype(self, g):
        return self.base.ask_type(g)

    def bit(self, g, i):
        return self.base.ask_bit(g, i) ^ self.nodes[g].flip[i]

    def prot(self, v):
        n = self.nodes[v]
        if n.prot is None:
            self.base.ask_prot(v)
        return n.prot

    def partner(self, v):
        n = self.nodes[v]
        if n.partner is None:
            self.base.ask_partner(v)
        return n.partner

    def is_output(self, g):
        n = self.nodes[g]
        if n.output or self.base.ask_is_zero(g):
            return True
        return any(self.is_output(o) for o in n.mout)

    # ---- operations
    def truth_table(self, g):
        n = self.nodes[g]
        if n.tt is not None:
            return n.tt
        t = self.gtype(g)
        f2 = n.flip[2]
        if t == 'xor':
            return tuple((s0 ^ s1 ^ f2) for s0 in (0, 1) for s1 in (0, 1))
        e0, e1 = self.bit(g, 0), self.bit(g, 1)
        return tuple((((s0 ^ e0) & (s1 ^ e1)) ^ f2) for s0 in (0, 1) for s1 in (0, 1))

    @staticmethod
    def tt_class(tt):
        if len(set(tt)) == 1:
            return ('const', tt[0])
        if tt[0] == tt[1] and tt[2] == tt[3]:
            return ('pass', 0, tt[0])
        if tt[0] == tt[2] and tt[1] == tt[3]:
            return ('pass', 1, tt[0])
        if tt[0] ^ tt[1] ^ tt[2] ^ tt[3] == 0:
            return ('xor',)
        return ('and',)

    def classify(self, g):
        """('const', c) | ('pass', slot, neg) | ('ident_pass', neg) | ('nondeg',) | ('and',) | ('xor',)."""
        n = self.nodes[g]
        a, b = self.inp(g, 0), self.inp(g, 1)
        ca, cb = is_const(a), is_const(b)
        if n.tt is None and not ca and not cb and a != b:
            return ('nondeg',)
        if n.tt is None and (ca != cb) and self.gtype(g) == 'and':
            k = 0 if ca else 1
            c = (a if ca else b)[1]
            if c == self.bit(g, k):
                return ('const', n.flip[2])
            o = 1 - k
            return ('pass', o, self.bit(g, o) ^ n.flip[2])
        tt = self.truth_table(g)
        if ca and cb:
            return ('const', tt[2 * a[1] + b[1]])
        if ca:
            sub = (tt[2 * a[1]], tt[2 * a[1] + 1])
            if sub[0] == sub[1]:
                return ('const', sub[0])
            return ('pass', 1, sub[0])
        if cb:
            sub = (tt[b[1]], tt[2 + b[1]])
            if sub[0] == sub[1]:
                return ('const', sub[0])
            return ('pass', 0, sub[0])
        if a == b:
            d = (tt[0], tt[3])
            if d[0] == d[1]:
                return ('const', d[0])
            return ('ident_pass', d[0])
        return self.tt_class(tt)

    def touch(self, v):
        self.touched.add(v)
        self.dirty.add(v)
        n = self.nodes[v]
        if n.kind == 'gate':
            for i in n.inp:
                if i is not None and not is_const(i):
                    self.dirty.add(i)

    def drop_succ(self, m, g):
        mn = self.nodes[m]
        mn.succ.remove(g)
        mn.bout -= 1
        self.touch(m)

    def remove_gate(self, g):
        n = self.nodes[g]
        n.removed = True
        self.removed.append(g)
        for i in n.inp:
            if i is not None and not is_const(i):
                self.drop_succ(i, g)
        n.inp = [None, None]
        n.succ = []

    def negate_slot(self, s, j, neg):
        if not neg:
            return
        sn = self.nodes[s]
        if sn.tt is not None:
            tt = sn.tt
            if j == 0:
                sn.tt = (tt[2], tt[3], tt[0], tt[1])
            else:
                sn.tt = (tt[1], tt[0], tt[3], tt[2])
        elif self.gtype(s) == 'and':
            sn.flip[j] ^= 1
        else:
            sn.flip[2] ^= 1

    # ---- transformations
    def t_const(self, g, c):
        n = self.nodes[g]
        if self.is_output(g):
            raise Vacuous()
        # unrevealed successors receive the constant anonymously: they are not
        # counted as removed, and any later decision that depends on them reveals them
        succs = list(n.succ)
        self.anon_effects += [g] + list(n.anon)
        n.anon = []
        for s in succs:
            sn = self.nodes[s]
            for j in (0, 1):
                if sn.inp[j] == g:
                    sn.inp[j] = (CONST, c)
            self.touch(s)
        n.succ = []
        self.const_removed.add(g)
        self.remove_gate(g)

    def t_pass(self, g, slot, neg):
        n = self.nodes[g]
        i = n.inp[slot]
        inode = self.nodes[i]
        # all unrevealed successor slots of g (and those g inherited) move to i
        self.anon_effects += [g] + list(n.anon)
        for o in [g] + list(n.anon):
            bo = self.base.nodes[o]
            if bo.out is not None and bo.out == len(bo.succ):
                continue
            if o not in inode.anon:
                inode.anon.append(o)
        n.anon = []
        for s in list(n.succ):
            sn = self.nodes[s]
            for j in (0, 1):
                if sn.inp[j] == g:
                    sn.inp[j] = i
                    self.negate_slot(s, j, neg)
                    inode.succ.append(s)
                    inode.bout += 1
            self.touch(s)
        # if g was the output, i becomes the output (decided lazily)
        inode.mout.append(g)
        n.succ = []
        self.touch(i)
        self.remove_gate(g)

    def try_rule(self, rule, g):
        n = self.nodes[g]
        if n.removed or n.kind != 'gate' or n.dist > self.R:
            return False
        if rule == 1:
            o = self.out_known(g)
            if o == 0 and not self.is_output(g):
                self.events.append(('N1', g))
                self.remove_gate(g)
                return True
            return False
        if rule == 4:
            return self.try_n4(g)
        cl = self.classify(g)
        if rule == 2:
            if cl[0] == 'const':
                self.events.append(('N2', g))
                self.t_const(g, cl[1])
                return True
            return False
        if rule == 3:
            if cl[0] == 'pass':
                self.events.append(('N3', g))
                self.t_pass(g, cl[1], cl[2])
                return True
            return False
        if rule == 5:
            if cl[0] == 'ident_pass':
                self.events.append(('N5', g))
                self.t_pass(g, 0, cl[1])
                return True
            return False
        return False

    def try_n4(self, g):
        """Transformation 4, applied only when decidable from known facts."""
        n = self.nodes[g]
        if self.out_known(g) != 1 or n.output or self.base.nodes[g].out == 0:
            return False
        if len(n.succ) != 1 or n.anon:
            return False
        a, b = n.inp
        if a is None or b is None or is_const(a) or is_const(b) or a == b:
            return False
        q = n.succ[0]
        if q == g:
            return False
        qn = self.nodes[q]
        qa, qb = qn.inp
        if qa is None or qb is None or qa == qb:
            return False
        for i_sh in (0, 1):
            shared = n.inp[i_sh]
            if shared in (qa, qb) and g in (qa, qb):
                self.events.append(('N4', g))
                other = n.inp[1 - i_sh]
                ttg = self.truth_table(g)
                ttq = self.truth_table(q)
                jg = 0 if qa == g else 1
                ja = 1 - jg
                new = [0, 0, 0, 0]
                for s_new in (0, 1):
                    for s_a in (0, 1):
                        gin = [0, 0]
                        gin[i_sh] = s_a
                        gin[1 - i_sh] = s_new
                        gval = ttg[2 * gin[0] + gin[1]]
                        qin = [0, 0]
                        qin[jg] = gval
                        qin[ja] = s_a
                        qslot = [0, 0]
                        qslot[jg] = s_new
                        qslot[ja] = s_a
                        new[2 * qslot[0] + qslot[1]] = ttq[2 * qin[0] + qin[1]]
                qn.tt = tuple(new)
                qn.inp[jg] = other
                self.nodes[other].succ.append(q)
                self.nodes[other].bout += 1
                self.touch(other)
                self.touch(q)
                n.succ = []
                self.remove_gate(g)
                return True
        return False

    def try_rule_guarded(self, rule, g):
        if not self.frugal:
            return self.try_rule(rule, g)
        if (rule, g) in self.blocked:
            return False
        snap = {k: v.clone() for k, v in self.nodes.items()}
        state = (list(self.removed), set(self.const_removed), set(self.touched),
                 set(self.dirty), list(self.events))
        try:
            return self.try_rule(rule, g)
        except Need as nd:
            # frugal mode: skip a transformation that needs an unknown fact and
            # remember the fact; the driver branches on it only if no action passes
            self.suggest.append(nd)
            self.nodes = snap
            (self.removed, self.const_removed, self.touched, self.dirty, self.events) = state
            self.blocked.add((rule, g))
            return False

    def normalize(self):
        while True:
            applied = False
            for rule in (1, 2, 3, 4, 5):
                for g in sorted(self.dirty, key=lambda v: self.rank.get(v, 10 ** 9)):
                    if self.try_rule_guarded(rule, g):
                        applied = True
                        break
                if applied:
                    break
            if not applied:
                return

    # ---- substitutions
    def clear_var(self, x):
        xn = self.nodes[x]
        xn.bout = -self.base.ask_out(x)
        xn.succ = []
        xn.anon = []

    def subst(self, x, kind, value, src=None):
        xn = self.nodes[x]
        if xn.kind != 'var':
            raise Illegal('substituted node %s is not a variable' % (xn.name or x))
        if self.out(x) == 0 and not self.prot(x):
            raise Illegal('substituted variable %s is not influential' % (xn.name or x))
        if xn.output:
            raise Vacuous()
        if kind == 'const':
            p = None
            if self.prot(x):
                p = self.partner(x)
            self.anon_effects += [x] + list(xn.anon)
            for s in list(xn.succ):
                sn = self.nodes[s]
                for j in (0, 1):
                    if sn.inp[j] == x:
                        sn.inp[j] = (CONST, value)
                self.touch(s)
            self.clear_var(x)
            if p is not None:
                self.q_dec += 1
                xn.prot = False
                xn.partner = None
                pn = self.nodes[p]
                pn.prot = False
                pn.partner = None
                self.touch(p)
            self.touch(x)
            return
        if self.prot(x):
            raise Illegal('%s substitution of protected variable %s (Lemma 3.1.1 items 2-3)' % (kind, xn.name or x))
        if src is None:
            raise Illegal('%s substitution without source' % kind)
        sn = self.nodes[src]
        if kind == 'affine':
            if sn.kind != 'var':
                raise Illegal('affine source %s is not an input (xor-reconstruction not supported)' % (sn.name or src))
            if src == x:
                raise Illegal('affine source equals substituted variable')
        elif kind == 'quadratic':
            if sn.kind != 'gate':
                raise Illegal('quadratic source %s is not a gate' % (sn.name or src))
            cl = self.classify(src)
            is_and = (cl[0] == 'and') or (cl[0] == 'nondeg' and self.gtype(src) == 'and')
            if not is_and:
                raise Illegal('quadratic source %s is not an and-type gate' % (sn.name or src))
            u, v = self.inp(src, 0), self.inp(src, 1)
            for w in (u, v):
                if is_const(w) or self.nodes[w].kind != 'var':
                    raise Illegal('quadratic source %s is not fed by two inputs' % (sn.name or src))
                if self.prot(w):
                    raise Illegal('quadratic source input %s already protected (read-once)' % (self.nodes[w].name or w))
            if x in (u, v):
                raise Illegal('quadratic source reads the substituted variable')
        else:
            raise Illegal('unknown substitution kind %s' % kind)
        if self.base.reaches(x, src):
            raise Illegal('source reachable from substituted variable (Prop. 3.4.2)')
        if sn.kind == 'var' and self.out(src) + self.out(x) == 2:
            self.subst_troubled += 2
        # unrevealed successors of x move to src as a block (as in Transformation 3)
        self.anon_effects += [x] + list(xn.anon)
        for o in [x] + list(xn.anon):
            bo = self.base.nodes[o]
            if bo.out is not None and bo.out == len(bo.succ):
                continue
            if o not in sn.anon:
                sn.anon.append(o)
        for s in list(xn.succ):
            tn = self.nodes[s]
            for j in (0, 1):
                if tn.inp[j] == x:
                    tn.inp[j] = src
                    self.negate_slot(s, j, value)
                    sn.succ.append(s)
                    sn.bout += 1
            self.touch(s)
        self.clear_var(x)
        self.touch(x)
        self.touch(src)
        if kind == 'quadratic':
            self.q_dec -= 1
            for w in (u, v):
                self.nodes[w].prot = True
                self.touch(w)
            self.nodes[u].partner = v
            self.nodes[v].partner = u

    # ---- measure
    def troubled_base(self, g):
        b = self.base
        n = b.nodes[g]
        if n.kind != 'gate':
            return False
        for k in (0, 1):
            i = n.inp[k]
            if i is not None and b.nodes[i].kind != 'var':
                return False
            if i is not None and b.nodes[i].out is not None and b.nodes[i].out != 2:
                return False
        if n.out is not None and n.out != 1:
            return False
        if n.gtype is not None and n.gtype != 'and':
            return False
        for k in (0, 1):
            i = b.ask_inp(g, k)
            if b.nodes[i].kind != 'var':
                return False
        if b.ask_out(g) != 1:
            return False
        for k in (0, 1):
            if b.ask_out(n.inp[k]) != 2:
                return False
        return b.ask_type(g) == 'and'

    def troubled_now(self, g):
        n = self.nodes[g]
        if n.kind != 'gate' or n.removed:
            return False
        for k in (0, 1):
            i = n.inp[k]
            if i is not None and (is_const(i) or self.nodes[i].kind != 'var'):
                return False
            if i is not None and self.out_known(i) is not None and self.out_known(i) != 2:
                return False
        ok = self.out_known(g)
        if ok is not None and ok != 1:
            return False
        a, b = self.inp(g, 0), self.inp(g, 1)
        if is_const(a) or is_const(b) or a == b:
            return False
        if self.nodes[a].kind != 'var' or self.nodes[b].kind != 'var':
            return False
        if self.out(a) != 2 or self.out(b) != 2:
            return False
        if self.out(g) != 1 or self.is_output(g):
            return False
        if n.tt is not None:
            return self.tt_class(n.tt)[0] == 'and'
        return self.gtype(g) == 'and'

    def pending(self):
        """Degenerate gates left unprocessed (beyond radius R, or blocked in frugal
        mode). A gate with a constant input or two identical inputs computes a
        constant or passing operation whatever its type, so Transformation 2, 3
        or 5 will remove it; a 0-gate that is not the output is removed by
        Transformation 1. Only known facts are used."""
        cnt = 0
        for g in self.touched:
            n = self.nodes[g]
            if n.kind != 'gate' or n.removed:
                continue
            a, b = n.inp
            if any(is_const(i) for i in n.inp) or (a is not None and a == b):
                cnt += 1
                continue
            try:
                if self.out_known(g) == 0 and not self.is_output(g):
                    cnt += 1
            except Need:
                continue
        return cnt

    def _infl_before(self, v):
        bn = self.base.nodes[v]
        if bn.succ or bn.prot is True:
            return True
        if bn.out is None or (bn.out == 0 and bn.prot is None):
            return None
        return bn.out >= 1 or bool(bn.prot)

    def _infl_after(self, v):
        n = self.nodes[v]
        if self.has_succ(v) or n.prot is True:
            return True
        o = self.out_known(v)
        if o is None:
            return None
        if o >= 1:
            return True
        if n.prot is None:
            return None
        return bool(n.prot)

    def influence_drop(self, substituted):
        """Lower bound on the drop of influential inputs; a fact is asked only
        when the bound would otherwise be lossy in the wrong direction."""
        b = self.base
        ivars = set(v for v in self.touched if self.nodes[v].kind == 'var') | set(substituted)
        i_dec = 0
        for v in ivars:
            ib = self._infl_before(v)
            ia = self._infl_after(v)
            if ib is not None and ia is not None:
                i_dec += int(ib) - int(ia)
                continue
            if ia is False:
                continue                      # term = ib >= 0: count 0
            if ib is True and self.out_known(v) is None:
                continue                      # term = 1 - ia >= 0: count 0 (bonus only)
            ib = b.ask_out(v) >= 1 or b.ask_prot(v)
            ia = self.has_succ(v) or self.out(v) >= 1 or self.prot(v)
            i_dec += int(ib) - int(ia)
        return i_dec

    def measure_conservative(self, substituted, subst_new_troubled):
        """Per-rule accounting (Prop. 3.4.3): every removed or pending gate is worth
        beta = 1 - 4 aT; the substitution step itself may add subst_new_troubled
        troubled gates (Prop. 3.4.2, with the source's own successors)."""
        i_dec = self.influence_drop(substituted)
        pend = self.pending()
        g = len(self.removed)
        return {'g': g, 't': -4 * g - subst_new_troubled, 'i': i_dec, 'q': self.q_dec,
                'pending': pend, 'mode': 'conservative'}

    def measure(self, substituted):
        """Exact accounting on the partially normalized circuit."""
        b = self.base
        for v in list(self.nodes):
            if self.nodes[v].anon:
                self.all_succ(v)
        g_rem = len(self.removed)
        cand = set(self.removed)
        for v in self.touched:
            if self.nodes[v].kind == 'gate':
                cand.add(v)
        for v in list(self.touched) + list(substituted):
            n = self.nodes[v]
            if n.kind != 'var':
                continue
            ob = b.ask_out(v)
            oa = self.out(v)
            if ob != oa and 2 in (ob, oa):
                cand.update(b.ask_all_succ(v))
                cand.update(n.succ)
        cand = sorted(cand, key=lambda v: self.rank.get(v, 0))
        t_before = sum(1 for g in cand if self.troubled_base(g))
        t_after = sum(1 for g in cand if self.troubled_now(g))
        i_dec = self.influence_drop(substituted)
        pend = self.pending()
        return {'g': g_rem, 't': t_before - t_after, 'i': i_dec, 'q': self.q_dec,
                'pending': pend, 't_before': t_before, 't_after': t_after, 'mode': 'exact'}


# ====================================================================== linear forms
TYPE_BOUNDS = {
    # coefficients of (1, aT, aI, aQ) with beta = 1 - 4 aT expanded (FGHK p.22-23)
    1: (Fr(0), Fr(0), Fr(3), Fr(0)),
    2: (Fr(0), Fr(0), Fr(2), Fr(0)),
    3: (Fr(4), Fr(-16), Fr(1), Fr(0)),
    4: (Fr(3), Fr(1), Fr(1), Fr(0)),
    5: (Fr(5), Fr(-20), Fr(1), Fr(-1)),
    6: (Fr(5), Fr(-20), Fr(2), Fr(1)),
    7: (Fr(2), Fr(-8), Fr(1), Fr(1)),
}


def gain_form(m):
    """Lower bound on Delta mu as coefficients of (1, aT, aI, aQ):
    g + aT*t + aI*i + aQ*q + beta*pending."""
    return (Fr(m['g'] + m['pending']), Fr(m['t'] - 4 * m['pending']), Fr(m['i']), Fr(m['q']))


def dominates(a, l):
    """a - l >= 0 for all 0 <= aT <= 1/4, aI >= 0, aQ >= 0."""
    d = [x - y for x, y in zip(a, l)]
    if d[2] < 0 or d[3] < 0:
        return False
    return d[0] >= 0 and d[0] + d[1] / 4 >= 0


def form_str(f):
    names = ['', 'aT', 'aI', 'aQ']
    out = []
    for c, nm in zip(f, names):
        if c == 0:
            continue
        out.append('%s%s' % (c, ('*' + nm) if nm else ''))
    return ' + '.join(out) if out else '0'
