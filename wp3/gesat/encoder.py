"""SAT encoding of 'a completion that no action discharges' for one certificate node
and one identification partition of its pattern (WP3.2).

Design and semantics: wp3/wp32_preregistration_2026-10-13.txt, Part 1 (E1-E12).
Nothing here is keyed to a case label: everything case-specific comes from the
JSON certificates through gecheck.checker (pattern compilation, partitions).

Universe = pool of slots: pattern slots (P), level-1 block (A, static size),
partner block (Q, one slot per pattern variable with an open partner), block B
(F_B slots, level >= 2).  See the pre-registration for the requirement /
overflow (OVF) semantics.
"""
from fractions import Fraction as Fr
import itertools

from .cnf import CNF, TRUE, FALSE
from gecheck.engine import TYPE_BOUNDS


def _int(x):
    assert Fr(x).denominator == 1
    return int(x)


class EncodingError(Exception):
    pass


class Instance:
    def __init__(self, tree, node, comp, FB, cap=3, mode='leaf', siblings=False):
        self.tree = tree
        self.node = node
        self.comp = comp
        self.cap = cap
        self.mode = mode
        self.c = CNF()
        self._E = {}
        self._attr = {}
        self._lookup = {}
        self.build_slots(FB)
        self.structure()
        self.ovf = self.c.new()
        self.sims = []
        chain = [node]
        m = node
        while m.parent is not None and m.inherit:
            m = m.parent
            chain.append(m)
        self.chain = chain
        for owner in chain:
            for ai, act in enumerate(owner.actions):
                steps = act['steps']
                choices = []
                for s in steps:
                    v = s.get('value', 0)
                    if isinstance(v, dict):
                        lit = self.triv_const(s)
                        choices.append([lit] if lit is not None else [FALSE, TRUE])
                    else:
                        choices.append([TRUE if v else FALSE])
                for combo in itertools.product(*choices):
                    self.sims.append(Sim(self, owner, ai, act, combo))
        self.ovf_constraints()
        self.pre_constraints()
        if siblings:
            self.sibling_constraints()
        if mode == 'internal':
            self.child_constraints()
        for sm in self.sims:
            self.c.add([-sm.vac])
            self.c.add([-sm.ok])

    def triv_const(self, step):
        """Performance (post-freeze, documented): for x <- c trivialising an
        and-gate that x feeds directly in the pattern, the only constant that can
        trivialise it is that gate's bit at x's slot; the other constant cannot
        credit the action, so only its vacuity check is dropped (sound: fewer
        exclusions). Returns the bit literal, or None (both constants tried)."""
        if step['kind'] != 'const':
            return None
        tname = step['value'].get('trivialize')
        if tname not in self.comp.names or step['var'] not in self.comp.names:
            return None
        tn = self.comp.nodes[self.comp.names[tname]]
        if tn.kind != 'gate' or not (tn.gtype == 'and' or tuple(tn.typedom) == ('and',)):
            return None
        xid = self.comp.names[step['var']]
        for j in (0, 1):
            if tn.inp[j] == xid:
                return self.bit[self.pid2slot[self.comp.names[tname]]][j]
        return None

    # ================================================================ slots
    def build_slots(self, FB):
        comp, cap = self.comp, self.cap
        c = self.c
        self.slots = []
        self.blk = []
        self.static_kind = []
        self.pid2slot = {}
        for nid in comp.order:
            n = comp.nodes[nid]
            self.pid2slot[nid] = len(self.slots)
            self.slots.append(nid)
            self.blk.append('P')
            self.static_kind.append(n.kind)
        P = list(range(len(self.slots)))
        # static bound on level-1 nodes
        KA = 0
        for nid in comp.order:
            n = comp.nodes[nid]
            KA += max(n.outdom) - len(n.succ)
            if n.kind == 'gate':
                KA += sum(1 for i in n.inp if i is None)
        self.KA = KA
        A = []
        for i in range(KA):
            A.append(len(self.slots))
            self.slots.append('A%d' % i)
            self.blk.append('A')
            self.static_kind.append(None)
        Q = []
        self.qslot = {}
        for nid in comp.order:
            n = comp.nodes[nid]
            if n.kind == 'var' and n.prot is not False and n.partner is None:
                s = len(self.slots)
                self.qslot[self.pid2slot[nid]] = s
                Q.append(s)
                self.slots.append('Q%s' % nid)
                self.blk.append('Q')
                self.static_kind.append('var')
        B = []
        for i in range(FB):
            B.append(len(self.slots))
            self.slots.append('B%d' % i)
            self.blk.append('B')
            self.static_kind.append(None)
        self.P, self.A, self.Q, self.B = P, A, Q, B
        self.N = len(self.slots)
        N = self.N
        self.used = [None] * N
        self.isg = [None] * N
        for s in range(N):
            if self.blk[s] == 'P':
                self.used[s] = TRUE
            else:
                self.used[s] = c.new()
            k = self.static_kind[s]
            if k == 'gate':
                self.isg[s] = TRUE
            elif k == 'var':
                self.isg[s] = FALSE
            else:
                self.isg[s] = c.new()
                c.add([self.used[s], -self.isg[s]])
        self.isv = [c.AND([self.used[s], -self.isg[s]]) for s in range(N)]
        self.gslots = [s for s in range(N) if self.isg[s] != FALSE]
        self.vslots = [s for s in range(N) if self.isg[s] != TRUE]
        # gate attributes
        self.isand = {}
        self.bit = {}
        for s in self.gslots:
            td = ('and', 'xor')
            if self.blk[s] == 'P':
                n = comp.nodes[self.slots[s]]
                td = n.typedom if n.gtype is None else (n.gtype,)
            if td == ('and',):
                self.isand[s] = TRUE
            elif td == ('xor',):
                self.isand[s] = FALSE
            else:
                self.isand[s] = c.new()
            self.bit[s] = (c.new(), c.new())
        # out-degree
        self.od = []
        for s in range(N):
            if self.blk[s] == 'P':
                dom = list(comp.nodes[self.slots[s]].outdom)
            else:
                dom = list(range(0, cap + 1))
            row = {}
            for d in range(cap + 1):
                row[d] = c.new() if d in dom else FALSE
            lits = [row[d] for d in range(cap + 1)]
            if self.blk[s] != 'P':
                # unused slot: out-degree 0
                c.add([self.used[s]] + [row[0]])
                for d in range(1, cap + 1):
                    c.add([self.used[s], -row[d]])
            c.add(lits)
            c.amo(lits)
            self.od.append(row)
        self.odge = []
        for s in range(N):
            ge = [TRUE]
            for k in range(1, cap + 2):
                ge.append(c.OR([self.od[s][d] for d in range(k, cap + 1)]))
            self.odge.append(ge)
        # protected flag
        self.prot = {}
        for s in self.vslots:
            if self.blk[s] == 'P':
                p = comp.nodes[self.slots[s]].prot
                self.prot[s] = TRUE if p is True else (FALSE if p is False else c.new())
            elif self.blk[s] == 'Q':
                self.prot[s] = self.used[s]
            else:
                self.prot[s] = c.new()
                c.add([self.isv[s], -self.prot[s]])
        # full flag
        self.full = {}
        for s in self.gslots:
            if self.blk[s] == 'P':
                self.full[s] = TRUE
            elif self.blk[s] == 'A':
                self.full[s] = self.isg[s]
            else:
                self.full[s] = c.new()
                c.add([self.isg[s], -self.full[s]])
        # input pointers
        self.inp = {}
        self.dom = {}
        PAQ = P + A + Q
        for g in self.gslots:
            for j in (0, 1):
                if self.blk[g] == 'P':
                    n = comp.nodes[self.slots[g]]
                    if n.inp[j] is not None:
                        dom = [self.pid2slot[n.inp[j]]]
                        lits = {dom[0]: TRUE}
                        self.dom[(g, j)] = dom
                        self.inp[(g, j)] = lits
                        continue
                    dom = [s for s in PAQ if s != g]
                elif self.blk[g] == 'A':
                    dom = [s for s in range(N) if s != g]
                else:
                    dom = [s for s in A + Q + B if s != g]
                lits = {}
                for v in dom:
                    if self.blk[g] == 'P' and (v, g) in [(self.pid2slot[a], self.pid2slot[b]) for a, b in comp.no_edge]:
                        continue
                    lits[v] = c.new()
                self.dom[(g, j)] = list(lits)
                self.inp[(g, j)] = lits
                L = list(lits.values())
                for l in L:
                    c.add([-l, self.full[g]])
                c.add([-self.full[g]] + L)
                c.amo(L)
                for v, l in lits.items():
                    c.add([-l, self.used[v]])
        # no_edge between pattern nodes where the target slot is generic: handled in E()
        self.readers = {s: [] for s in range(N)}
        for (g, j), lits in self.inp.items():
            for v, l in lits.items():
                self.readers[v].append((g, j, l))

    # ================================================================ helpers
    def E(self, u, v):
        """u feeds v in the original circuit (revealed edge)."""
        key = (u, v)
        if key in self._E:
            return self._E[key]
        if self.isg[v] == FALSE:
            r = FALSE
        else:
            r = self.c.OR([self.inp[(v, j)].get(u, FALSE) for j in (0, 1)])
        self._E[key] = r
        return r

    def lookup(self, g, j, fn, tag):
        """literal equal to fn(target of pointer (g, j)); FALSE when not full."""
        key = (g, j, tag)
        if key in self._lookup:
            return self._lookup[key]
        lits = self.inp[(g, j)]
        if len(lits) == 1 and list(lits.values())[0] == TRUE:
            r = fn(list(lits)[0])
        else:
            r = self.c.new()
            self.c.add([self.full[g], -r])
            for v, l in lits.items():
                self.c.imp_eq([l], r, fn(v))
        self._lookup[key] = r
        return r

    # ================================================================ structure
    def structure(self):
        c, N, cap = self.c, self.N, self.cap
        # identical inputs (Transformation 5) are not normalized
        for g in self.gslots:
            for v, l in self.inp[(g, 0)].items():
                l2 = self.inp[(g, 1)].get(v)
                if l2 is not None:
                    c.add([-l, -l2])
        # reader count <= out-degree; hidden successors
        self.cge = {}
        self.extpos = {}
        self.ext_ge = {}
        for v in range(N):
            rl = [l for (_, _, l) in self.readers[v]]
            cge = c.counter(rl, cap + 1)
            self.cge[v] = cge
            for k in range(1, cap + 2):
                c.add([-cge[k], self.odge[v][k]])
            self.extpos[v] = c.OR([c.AND([self.odge[v][k], -cge[k]]) for k in range(1, cap + 1)])
            eg = [TRUE]
            for k in range(1, cap + 1):
                terms = [c.AND([self.od[v][d], -cge[d - k + 1]]) for d in range(k, cap + 1)]
                eg.append(c.OR(terms))
            self.ext_ge[v] = eg
            if self.blk[v] == 'P':
                c.add([-self.extpos[v]])       # pattern nodes: every successor revealed
        # level 1: block-A slots are adjacent to the pattern
        for a in self.A:
            adj = []
            for p in self.P:
                adj.append(self.E(p, a))
                adj.append(self.E(a, p))
            c.add([-self.used[a]] + adj)
        # pattern no_edge with generic targets
        for a, b in self.comp.no_edge:
            sa, sb = self.pid2slot[a], self.pid2slot[b]
            c.add([-self.E(sa, sb)])
        # sum_ge on pattern nodes
        for ids, k in self.comp.sum_ge:
            ss = [self.pid2slot[i] for i in ids]
            combos = []
            for ds in itertools.product(range(cap + 1), repeat=len(ss)):
                if sum(ds) >= k:
                    combos.append(c.AND([self.od[s][d] for s, d in zip(ss, ds)]))
            c.add(combos)
        # at most one output (gate of out-degree 0)
        self.outsel = {g: c.AND([self.isg[g], self.used[g], self.od[g][0]]) for g in self.gslots}
        c.amo(list(self.outsel.values()))
        # acyclicity: binary rank on gate slots, rank(input) < rank(gate)
        L = len(self.gslots) + 1
        nb = max(1, L.bit_length())
        self.rk = {g: [c.new() for _ in range(nb)] for g in self.gslots}
        zero = [FALSE] * nb
        lt_cache = {}

        def lt(a, b):
            # a < b, most significant bit first
            res = FALSE
            eq = TRUE
            for x, y in zip(reversed(a), reversed(b)):
                res = c.OR([res, c.AND([eq, -x, y])])
                eq = c.AND([eq, c.EQV(x, y)])
            return res
        for (g, j), lits in self.inp.items():
            for u, l in lits.items():
                key = (u, g)
                if key not in lt_cache:
                    if u in self.rk:
                        # a variable slot has rank 0
                        ru = [c.AND([self.isg[u], r]) for r in self.rk[u]] if self.isg[u] != TRUE else self.rk[u]
                    else:
                        ru = zero
                    lt_cache[key] = lt(ru, self.rk[g])
                c.add([-l, lt_cache[key]])
        # Transformation 4 configuration on the revealed part of the original circuit:
        # a revealed 1-gate g whose successor q also reads one of g's inputs
        # post-freeze fix 1: g ranges over the eligible gates (pattern and block A)
        # and q over every full gate (two controls replayed as engine-pruned 'N4')
        # post-freeze fix 3: block-B 1-gates as well (control m_dropped_pre_4 was
        # replayed as an engine-pruned N4 configuration with g in block B)
        for g in self.gslots:
            od1 = self.od[g][1]
            if od1 == FALSE:
                continue
            for q in self.gslots:
                if q == g:
                    continue
                for k in (0, 1):
                    lq = self.inp[(q, k)].get(g)
                    if lq is None:
                        continue
                    for jg in (0, 1):
                        for v, lv in self.inp[(q, 1 - k)].items():
                            lg = self.inp[(g, jg)].get(v)
                            if lg is None:
                                continue
                            c.add([-od1, -lq, -lv, -lg])
        # partners
        self.pt = {}
        V = self.vslots
        for i, v in enumerate(V):
            for w in V[i + 1:]:
                if self.blk[v] == 'P' and self.blk[w] == 'P':
                    pv = self.comp.nodes[self.slots[v]].partner
                    pw = self.comp.nodes[self.slots[w]].partner
                    if pv == self.slots[w]:
                        lit = TRUE
                    elif pv is not None or pw is not None:
                        lit = FALSE
                    else:
                        lit = c.new()
                else:
                    lit = c.new()
                    for x in (v, w):
                        if self.blk[x] == 'P' and self.comp.nodes[self.slots[x]].partner is not None:
                            lit = FALSE
                if lit not in (TRUE, FALSE):
                    c.add([-lit, self.isv[v]])
                    c.add([-lit, self.isv[w]])
                self.pt[(v, w)] = lit
                self.pt[(w, v)] = lit
        self.ptx = {}
        for v in V:
            if self.blk[v] == 'P':
                self.ptx[v] = FALSE
            else:
                self.ptx[v] = c.new()
                c.add([-self.ptx[v], self.isv[v]])
            plist = [self.pt[(v, w)] for w in V if w != v] + [self.ptx[v]]
            c.amo(plist)
            # protected <-> has a partner
            c.add([-self.prot[v]] + plist)
            for l in plist:
                c.add([-l, self.prot[v]])
        for p, q in self.qslot.items():
            c.add([-self.used[q], self.pt[(p, q)]])
            c.add([self.used[q], -self.pt[(p, q)]])
        # influential before
        self.infl0 = {v: c.AND([self.isv[v], c.OR([self.odge[v][1], self.prot[v]])]) for v in V}
        # troubled before (full gates)
        self.q2 = {v: c.AND([self.isv[v], self.od[v][2]]) for v in range(self.N)}
        self.tb = {}
        for g in self.gslots:
            ins = [self.lookup(g, j, lambda v: self.q2[v], 'q2') for j in (0, 1)]
            self.tb[g] = c.AND([self.full[g], self.isand[g], self.od[g][1]] + ins)
        # symmetry breaking inside blocks A and B
        for blkname, others in (('A', self.P), ('B', self.P + self.A)):
            S = self.A if blkname == 'A' else self.B
            sig = {}
            for s in S:
                bits = [self.used[s], self.isg[s]]
                for o in others:
                    bits.append(self.E(o, s))
                    bits.append(self.E(s, o))
                sig[s] = bits
            for s1, s2 in zip(S, S[1:]):
                c.lex_geq(sig[s1], sig[s2])

    # ================================================================ requirements
    def ovf_constraints(self):
        c = self.c
        # R1: successors revealed for nodes removed / substituted / with a degree
        # change involving 2 (variables); R2: gates with a degree change are full
        self.rsucc = {}
        for v in range(self.N):
            # only simulations that can credit their action (legal, targets
            # trivialised) need exact accounting, hence revealed successors
            terms = [c.AND([sm.legal, sm.triv, sm.rsucc_term(v)]) for sm in self.sims if sm.passes]
            self.rsucc[v] = c.OR(terms) if self.blk[v] != 'P' else TRUE
        self.rfull = {}
        for g in self.B:
            if self.isg[g] == FALSE:
                continue
            self.rfull[g] = c.OR([c.AND([sm.legal, sm.triv, sm.rfull_term(g)]) for sm in self.sims if sm.passes])
        unmet = []
        for v in range(self.N):
            if self.blk[v] != 'P':
                unmet.append(c.AND([self.rsucc[v], self.extpos[v]]))
        for g, r in self.rfull.items():
            unmet.append(c.AND([r, -self.full[g]]))
        # partner of a substituted protected variable must be revealed
        for sm in self.sims:
            for x in sm.subst_slots:
                if x in self.ptx and sm.passes:
                    unmet.append(c.AND([sm.legal, sm.triv, self.prot[x], self.ptx[x]]))
        u = c.OR(unmet)
        c.add([-self.ovf, u])
        c.add([self.ovf, -u])
        for b in self.B:
            c.add([-self.ovf, self.used[b]])
        # justification of block-B slots (no junk)
        rr = {}
        for g in self.B:
            if self.isg[g] == FALSE:
                continue
            reads = [self.lookup(g, j, lambda v: self.rsucc[v], 'rsucc') for j in (0, 1)]
            rr[g] = c.OR(reads)
            c.add([-self.full[g], rr[g], self.rfull[g]])
        for b in self.B:
            just = [c.AND([self.full[g], l]) for (g, j, l) in self.readers[b]]
            if b in rr:
                just.append(c.AND([self.full[b], rr[b]]))
            for w in self.vslots:
                if w != b and (w, b) in self.pt and self.blk[w] != 'B':
                    just.append(self.pt[(w, b)])
            c.add([-self.used[b]] + just)

    # ================================================================ embeddings
    def attr_lit(self, cn, s):
        key = (cn['kind'], tuple(sorted(cn['type'])) if cn['type'] else None, cn['lo'], cn['hi'], cn['prot'], s)
        if key in self._attr:
            return self._attr[key]
        c = self.c
        parts = []
        if cn['kind'] == 'var':
            parts.append(self.isv[s])
        else:
            parts.append(c.AND([self.used[s], self.isg[s]]))
        if cn['type'] is not None and cn['kind'] == 'gate' and s in self.isand:
            if cn['type'] == {'and'}:
                parts.append(self.isand[s])
            elif cn['type'] == {'xor'}:
                parts.append(-self.isand[s])
        lo, hi = cn['lo'], cn['hi']
        if hi is None:
            hi = self.cap
        if lo > 0 or hi < self.cap:
            parts.append(c.OR([self.od[s][d] for d in range(lo, min(hi, self.cap) + 1)]))
        if cn['prot'] is not None:
            if s in self.prot:
                parts.append(self.prot[s] if cn['prot'] else -self.prot[s])
            else:
                parts.append(FALSE)
        r = c.AND(parts)
        self._attr[key] = r
        return r

    def forbid_embedding(self, pat, fixed):
        """Add clauses forbidding every embedding of pattern `pat` (a checker
        Pattern, canonical) that extends `fixed` (name -> slot)."""
        c = self.c
        names = [n for n in pat.nodes if n not in fixed]
        # pure leaves: a new node whose only relation is one edge into a gate
        # (mapped or not) and node attributes
        deg = {n: 0 for n in pat.nodes}
        for u, v in pat.edges:
            deg[u] += 1
            deg[v] += 1
        involved = set()
        for e in pat.no_edge + pat.distinct + pat.partner:
            involved.update(e)
        for e, _k in pat.sum_ge:
            involved.update(e)
        leaves = {}
        for n in names:
            if deg[n] == 1 and n not in involved:
                es = [(u, v) for u, v in pat.edges if u == n]
                if es and es[0][1] != n:
                    leaves[n] = es[0][1]
        # a leaf is kept only if every pattern edge into its target comes from a
        # leaf (then distinct input slots encode 'two edges, two sources')
        changed = True
        while changed:
            changed = False
            for n, tgt in list(leaves.items()):
                srcs = [u for u, v in pat.edges if v == tgt]
                if tgt in leaves or any(u not in leaves for u in srcs):
                    del leaves[n]
                    changed = True
        core = [n for n in names if n not in leaves]
        # order core names: adjacent to mapped first
        order = []
        have = set(fixed)
        rest = list(core)
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

        def cands(n, M):
            cn = pat.nodes[n]
            out = None
            for u, v in pat.edges:
                if v == n and u in M:
                    cs = [g for g in self.gslots if any(M[u] in self.inp[(g, j)] for j in (0, 1))]
                    out = cs if out is None else [x for x in out if x in cs]
                if u == n and v in M:
                    g = M[v]
                    if g not in self.isand and self.isg[g] == FALSE:
                        return []
                    cs = list(dict.fromkeys(self.dom.get((g, 0), []) + self.dom.get((g, 1), [])))
                    out = cs if out is None else [x for x in out if x in cs]
            if out is None:
                out = list(range(self.N))
            if cn['kind'] == 'var':
                out = [s for s in out if self.isg[s] != TRUE]
            else:
                out = [s for s in out if self.isg[s] != FALSE]
            return out

        def emit(M):
            conds = []
            for n, s in M.items():
                conds.append(self.attr_lit(pat.nodes[n], s))
            for u, v in pat.edges:
                if u in M and v in M:
                    conds.append(self.E(M[u], M[v]))
            for (u1, v1), (u2, v2) in itertools.combinations(pat.edges, 2):
                if v1 == v2 and u1 in M and u2 in M and M[u1] == M[u2]:
                    return
            for u, v in pat.no_edge:
                if u in M and v in M:
                    conds.append(-self.E(M[u], M[v]))
            for u, v in pat.distinct:
                if M.get(u) is not None and M.get(u) == M.get(v):
                    return
            for u, v in pat.partner:
                if M[u] == M[v] or (M[u], M[v]) not in self.pt:
                    return
                conds.append(self.pt[(M[u], M[v])])
            for names_, k in pat.sum_ge:
                ss = [M[x] for x in names_]
                combos = []
                for ds in itertools.product(range(self.cap + 1), repeat=len(ss)):
                    if sum(ds) >= k:
                        combos.append(c.AND([self.od[s][d] for s, d in zip(ss, ds)]))
                conds.append(c.OR(combos))
            # leaves: grouped by the gate they feed; distinct input slots
            byg = {}
            for lf, g in leaves.items():
                byg.setdefault(g, []).append(lf)
            for gname, lfs in byg.items():
                if gname not in M:
                    raise EncodingError('leaf into unmapped node')
                g = M[gname]
                if self.isg[g] == FALSE:
                    return
                if len(lfs) > 2:
                    return
                alts = []
                for perm in itertools.permutations((0, 1), len(lfs)):
                    part = []
                    for lf, j in zip(lfs, perm):
                        cn = pat.nodes[lf]
                        part.append(self.lookup(g, j, lambda v, cn=cn: self.attr_lit(cn, v),
                                                ('attr', cn['kind'], tuple(sorted(cn['type'])) if cn['type'] else None,
                                                 cn['lo'], cn['hi'], cn['prot'])))
                    alts.append(c.AND(part))
                conds.append(c.OR(alts))
            c.add([-x for x in conds])

        def rec(i, M):
            if i == len(order):
                emit(M)
                return
            n = order[i]
            for s in cands(n, M):
                M[n] = s
                rec(i + 1, M)
                del M[n]
        rec(0, dict(fixed))

    def pre_constraints(self):
        from gecheck import checker as ck
        for cid, tp in ck.node_pre(self.tree, self.node):
            self.forbid_embedding(tp, {})

    def sibling_constraints(self):
        """Option (post-freeze, documented): every case assumes that the earlier
        cases fail (FGHK p.23). For the node and each ancestor reached by
        inheritance, the patterns of the earlier siblings are forbidden with the
        shared names fixed (and the parent's declared symmetries), exactly as a
        child is matched. Not applied by the WP3.1 engine."""
        m = self.node
        while m.parent is not None and m.inherit:
            par = m.parent
            sigmas = [{}] + par.symmetries
            for sib in par.children:
                if sib is m:
                    break
                members = sib.children if sib.kind == 'union' else [sib]
                for mem in members:
                    shared = [nm for nm in mem.full.nodes if nm in self.comp.names]
                    for sg in sigmas:
                        fixed = {}
                        bad = False
                        for nm in shared:
                            src = sg.get(nm, nm)
                            if src not in self.comp.names:
                                bad = True
                                break
                            fixed[nm] = self.pid2slot[self.comp.names[src]]
                        if bad:
                            continue
                        self.forbid_embedding(mem.full, fixed)
            m = par

    def child_constraints(self):
        n = self.node
        sigmas = [{}] + n.symmetries
        for ch in n.children:
            members = ch.children if ch.kind == 'union' else [ch]
            for mem in members:
                shared = [nm for nm in mem.full.nodes if nm in self.comp.names]
                for sg in sigmas:
                    fixed = {}
                    bad = False
                    for nm in shared:
                        src = sg.get(nm, nm)
                        if src not in self.comp.names:
                            bad = True
                            break
                        fixed[nm] = self.pid2slot[self.comp.names[src]]
                    if bad:
                        continue
                    self.forbid_embedding(mem.full, fixed)

    def slot_of(self, name):
        return self.pid2slot[self.comp.names[name]]


# ==================================================================== simulation
class Sim:
    """One (action, constants) simulation: substitutions, per-step normalization
    passes (Transformations 1, 2, 3, 5 on eligible gates), measure, verdict."""

    def __init__(self, I, owner, ai, act, combo):
        self.I = I
        self.owner = owner
        self.act = act
        self.combo = combo
        self.name = '%s/%s/%s' % (owner.id, act.get('name', ai), ''.join('0' if v == FALSE else ('1' if v == TRUE else 'b') for v in combo))
        c = I.c
        self.E = [s for s in I.gslots if I.blk[s] in ('P', 'A')]     # eligible
        self.Eset = set(self.E)
        self.passes = []
        self.subst = {}            # slot -> ('const', c) | ('node', src, c)
        self.subst_slots = []
        legal_all = TRUE
        triv_all = TRUE
        self.vac = FALSE
        self.q_terms = []          # (+1 literal list, -1 count)
        q_plus = []
        q_minus = 0
        st_lits = []
        prev = None
        legal_prefix = TRUE
        triv_prefix = TRUE
        for k, (step, val) in enumerate(zip(act['steps'], combo)):
            var = step['var']
            if var not in I.comp.names:
                legal_all = FALSE
                break
            x = I.slot_of(var)
            kind = step['kind']
            src = None
            if step.get('src'):
                if step['src'] not in I.comp.names:
                    legal_all = FALSE
                    break
                src = I.slot_of(step['src'])
            # legality (state before this step)
            if I.static_kind[x] != 'var' or x in self.subst:
                legal = FALSE
            else:
                infl = c.OR([self.out_ge(prev, x, 1), self.prot_at(prev, x)])
                legal = infl
                if kind != 'const':
                    legal = c.AND([legal, -self.prot_at(prev, x)])
                if kind == 'affine':
                    if src is None or I.static_kind[src] != 'var' or src == x or src in self.subst:
                        legal = FALSE
                elif kind == 'quadratic':
                    if src is None or I.static_kind[src] != 'gate' or k != 0:
                        legal = FALSE
                    else:
                        conds = [I.isand[src]]
                        for j in (0, 1):
                            conds.append(I.lookup(src, j, lambda v: I.isv[v], 'isv'))
                            conds.append(-I.lookup(src, j, lambda v: I.prot.get(v, FALSE), 'prot'))
                            conds.append(-I.inp[(src, j)].get(x, FALSE))
                        legal = c.AND([legal] + conds)
                elif kind != 'const':
                    legal = FALSE
            # output is the substituted variable -> vacuous (engine raises Vacuous)
            if prev is not None:
                self.vac = c.OR([self.vac, c.AND([legal_prefix, triv_prefix, legal, prev.isout[x]])])
            # q accounting and Prop. 3.4.2 term
            if kind == 'const':
                q_plus.append(self.prot_at(prev, x))
            elif kind == 'quadratic':
                q_minus += 1
            if kind == 'affine' and src is not None and I.static_kind[src] == 'var':
                st_lits.append(c.OR([c.AND([self.out_eq(prev, src, a), self.out_eq(prev, x, 2 - a)])
                                     for a in range(0, 3)]))
            # record substitution
            if kind == 'const':
                self.subst[x] = ('const', val)
            else:
                self.subst[x] = ('node', src, val)
            self.subst_slots.append(x)
            p = Pass(self, k, prev, x, kind, src, val)
            self.passes.append(p)
            legal_prefix = c.AND([legal_prefix, legal])
            self.vac = c.OR([self.vac, c.AND([legal_prefix, triv_prefix, p.vac])])
            v = step.get('value', 0)
            if isinstance(v, dict) and 'trivialize' in v:
                tname = v['trivialize']
                if tname in I.comp.names and I.slot_of(tname) in self.Eset:
                    t = I.slot_of(tname)
                    triv = p.cr[t]
                else:
                    triv = FALSE
                triv_prefix = c.AND([triv_prefix, triv])
            prev = p
        legal_all = c.AND([legal_all, legal_prefix])
        triv_all = triv_prefix
        self.legal = legal_all
        self.triv = triv_all
        if not self.passes:
            self.ok = FALSE
            return
        last = self.passes[-1]
        self.last = last
        # ---------------------------------------------------------- measure
        removed = [last.removed[u] for u in self.E]
        pend = []
        for g in I.B:
            if I.isg[g] == FALSE:
                continue
            pend.append(c.AND([I.full[g], c.OR([last.cc[(g, 0)], last.cc[(g, 1)], last.sm[g],
                                                 c.AND([-last.oge[g][1], -last.isout[g]])])]))
        # post-freeze fix 2: Transformation 4 is not simulated after the
        # substitution, but if some eligible alive 1-gate is useless in the final
        # state (its only reader also reads one of its resolved inputs), one more
        # gate will be removed (worth beta by Prop. 3.4.3): credited like a pending gate
        n4c = []
        for g in self.E:
            reads = []
            for q in I.gslots:
                if q == g:
                    continue
                for k in (0, 1):
                    rq = last.ct[(q, k)][g]
                    for jg in (0, 1):
                        s = c.new()
                        c.add([-last.cc[(q, 1 - k)], -s])
                        for w in range(I.N):
                            c.imp_eq([last.ct[(q, 1 - k)][w]], s, last.ct[(g, jg)][w])
                        reads.append(c.AND([last.falive[q], rq, s]))
            n4c.append(c.AND([last.falive[g], last.oge[g][1], -last.oge[g][2], -last.isout[g], c.OR(reads)]))
        pend.append(c.OR(n4c))
        self.n4credit = pend[-1]
        lost, gained = [], []
        for v in I.vslots:
            if v in self.subst:
                inflK = FALSE
            else:
                inflK = c.AND([I.isv[v], c.OR([last.oge[v][1], last.prot[v]])])
            lost.append(c.AND([I.infl0[v], -inflK]))
            gained.append(c.AND([-I.infl0[v], inflK]))
        plus, minus = [], []
        for g in I.gslots:
            ta = last.ta[g]
            plus.append(c.AND([I.tb[g], -ta]))
            minus.append(c.AND([-I.tb[g], ta]))
        st2 = c.OR(st_lits) if st_lits else FALSE        # st = 2 * st2
        qcount = c.counter(q_plus, len(q_plus))          # q = qcount - q_minus

        def q_ge(Lq):
            need = Lq + q_minus
            if need <= 0:
                return TRUE
            if need > len(q_plus):
                return FALSE
            return qcount[need]
        bounds = [tuple(_int(x) for x in TYPE_BOUNDS[t]) for t in act['types']]
        L0max = max(b[0] for b in bounds)
        LImax = max(b[2] for b in bounds)
        Kmax = max(4 * b[0] + b[1] for b in bounds)
        CAPN = 8      # more than CAPN new troubled gates / gained inputs: not credited (sound)
        rp = c.counter(removed + pend, max(L0max, 0))
        gn = c.counter(gained, CAPN + 1)
        lc = c.counter(lost, max(LImax, 0) + CAPN)
        mn = c.counter(minus, CAPN + 1)
        xc = c.counter(removed * 4 + plus, max(Kmax, 0) + CAPN)

        def diff_ge(pc, nc, K):
            # sum(pos) - sum(neg) >= K, with sum(neg) <= CAPN
            alts = []
            for m in range(0, CAPN + 1):
                need = K + m
                pos_ok = TRUE if need <= 0 else pc[need]
                alts.append(c.AND([-nc[m + 1], pos_ok] + ([nc[m]] if m > 0 else [])))
            return c.OR(alts)
        self.dom_lits = {}
        oks = []
        for t, (L0, LT, LI, LQ) in zip(act['types'], bounds):
            iok = diff_ge(lc, gn, LI)
            qok = q_ge(LQ)
            gp = TRUE if L0 <= 0 else rp[L0]
            K = 4 * L0 + LT
            if K <= -2:
                cons_t = TRUE
            elif K <= 0:
                cons_t = -st2
            else:
                cons_t = FALSE
            ex_t = diff_ge(xc, mn, K)
            dcons = c.AND([iok, qok, gp, cons_t])
            dex = c.AND([iok, qok, gp, ex_t, -I.ovf])
            self.dom_lits[t] = (dcons, dex)
            oks.append(c.OR([dcons, dex]))
        self.ok = c.AND([legal_all, triv_all, c.OR(oks)])

    # ---- state accessors (prev is None: original circuit)
    def out_ge(self, prev, v, k):
        if prev is None:
            return self.I.odge[v][k]
        return prev.oge[v][k]

    def out_eq(self, prev, v, a):
        if a < 0:
            return FALSE
        return self.I.c.AND([self.out_ge(prev, v, a), -self.out_ge(prev, v, a + 1)])

    def prot_at(self, prev, v):
        if prev is None:
            return self.I.prot.get(v, FALSE)
        return prev.prot.get(v, FALSE)

    def rsucc_term(self, v):
        c = self.I.c
        terms = []
        if v in self.subst:
            terms.append(TRUE)
        for p in self.passes:
            if v in self.Eset:
                terms.append(c.AND([self.I.isg[v], p.fremoved[v]]))
            if v in self.I.prot:
                ch = c.AND([self.I.isv[v], -self.same_out(p, v),
                            c.OR([self.I.od[v][2], c.AND([p.oge[v][2], -p.oge[v][3]])])])
                terms.append(ch)
        return c.OR(terms)

    def rfull_term(self, g):
        return self.I.c.OR([-self.same_out(p, g) for p in self.passes] + [FALSE])

    def same_out(self, p, v):
        c = self.I.c
        key = ('same_out', v)
        if key in p.cache:
            return p.cache[key]
        r = c.AND([c.EQV(self.I.odge[v][k], p.oge[v][k]) for k in range(1, self.I.cap + 2)])
        p.cache[key] = r
        return r


class Pass:
    """State after substitution step k and normalization."""

    def __init__(self, sim, k, prev, x, kind, src, val):
        I = sim.I
        c = I.c
        cap = I.cap
        N = I.N
        self.cache = {}
        E = sim.E
        Eset = sim.Eset
        # ---------------- statuses of eligible gates
        st = {}
        for u in E:
            st[u] = dict(al=c.new(), cr=c.new(), cv=c.new(), p0=c.new(), p1=c.new(), pn=c.new(), n1=c.new())
            s = st[u]
            g = I.isg[u]
            for key in ('al', 'cr', 'p0', 'p1', 'n1'):
                c.add([g, -s[key]])
            c.add([-g, s['al'], s['cr'], s['p0'], s['p1']])
            c.amo([s['al'], s['cr'], s['p0'], s['p1']])
            c.add([-s['n1'], s['al']])
        self.st = st
        # ---------------- resolved inputs of full gates
        cur = {}
        ct = {}
        self.cc = {}
        cval = {}
        cneg = {}
        for g in I.gslots:
            for j in (0, 1):
                tl = {w: c.new() for w in range(N)}
                ct[(g, j)] = tl
                self.cc[(g, j)] = c.new()
                cval[(g, j)] = c.new()
                cneg[(g, j)] = c.new()
                c.add([I.full[g], -self.cc[(g, j)]])
                for w, l in tl.items():
                    c.add([I.full[g], -l])
                c.amo(list(tl.values()) + [self.cc[(g, j)]])
        # resolution of eligible slots: rt (target), rc (const), rval, rneg
        rt, rc, rval, rneg = {}, {}, {}, {}
        for u in E:
            rt[u] = {w: c.new() for w in range(N)}
            rc[u] = c.new()
            rval[u] = c.new()
            rneg[u] = c.new()
            c.amo(list(rt[u].values()) + [rc[u]])
            s = st[u]
            # a variable in an eligible slot resolves to itself
            c.add([I.isg[u], rt[u][u]])
            c.add([I.isg[u], -rc[u]])
            c.add([I.isg[u], -rneg[u]])
            c.add([-s['al'], rt[u][u]])
            c.add([-s['al'], -rc[u]])
            c.add([-s['al'], -rneg[u]])
            c.add([-s['cr'], rc[u]])
            c.imp_eq([s['cr']], rval[u], s['cv'])
            for j, pk in ((0, 'p0'), (1, 'p1')):
                for w in range(N):
                    c.imp([s[pk], ct[(u, j)][w]], rt[u][w])
                c.imp_eq([s[pk]], rc[u], self.cc[(u, j)])
                c.imp_eq([s[pk]], rneg[u], c.XOR(cneg[(u, j)], s['pn']))
        self.rt, self.rc = rt, rc
        # subst map at this step (cumulative)
        subst = dict(sim.subst)
        # cur = res(input)
        for (g, j), lits in I.inp.items():
            T = ct[(g, j)]
            for v, l in lits.items():
                if v in subst:
                    sv = subst[v]
                    if sv[0] == 'const':
                        c.add([-l, self.cc[(g, j)]])
                        c.imp_eq([l], cval[(g, j)], sv[1])
                    else:
                        c.add([-l, T[sv[1]]])
                        c.imp_eq([l], cneg[(g, j)], sv[2])
                elif v in Eset:
                    for w in range(N):
                        c.imp([l, rt[v][w]], T[w])
                    c.imp_eq([l], self.cc[(g, j)], rc[v])
                    c.imp_eq([l], cval[(g, j)], rval[v])
                    c.imp_eq([l], cneg[(g, j)], rneg[v])
                else:
                    c.add([-l, T[v]])
                    c.add([-l, -cneg[(g, j)]])
        self.ct = ct
        # same resolved target
        self.sm = {}
        for g in I.gslots:
            r = c.new()
            c.add([-self.cc[(g, 0)], -r])
            c.add([-self.cc[(g, 1)], -r])
            for w in range(N):
                c.imp_eq([ct[(g, 0)][w]], r, ct[(g, 1)][w])
            c.add([I.full[g], -r])
            self.sm[g] = r
        # ---------------- classification of eligible gates
        for u in E:
            s = st[u]
            g = I.isg[u]
            frozen = FALSE
            if prev is not None:
                ps = prev.st[u]
                frozen = c.OR([ps['cr'], ps['p0'], ps['p1'], ps['n1']])
                for key in ('al', 'cr', 'cv', 'p0', 'p1', 'pn'):
                    c.imp_eq([frozen], s[key], ps[key])
                c.add([-ps['n1'], s['n1']])
            a = I.isand[u]
            e0, e1 = I.bit[u]
            c0, c1 = self.cc[(u, 0)], self.cc[(u, 1)]
            v0, v1 = cval[(u, 0)], cval[(u, 1)]
            n0, n1_ = cneg[(u, 0)], cneg[(u, 1)]
            sm = self.sm[u]
            pre = [g, -frozen]
            # both constant
            f_and = c.AND([c.XOR(v0, e0), c.XOR(v1, e1)])
            f_xor = c.XOR(v0, v1)
            bc = c.AND(pre + [c0, c1])
            c.imp([bc], s['cr'])
            c.imp_eq([bc], s['cv'], c.ITE(a, f_and, f_xor))
            # input 0 constant
            k0 = c.AND(pre + [c0, -c1])
            triv0 = c.AND([a, c.EQV(v0, e0)])
            c.imp([k0, triv0], s['cr'])
            c.imp([k0, triv0], -s['cv'])
            c.imp([k0, -triv0], s['p1'])
            c.imp_eq([k0, -triv0], s['pn'], c.ITE(a, e1, v0))
            # input 1 constant
            k1 = c.AND(pre + [-c0, c1])
            triv1 = c.AND([a, c.EQV(v1, e1)])
            c.imp([k1, triv1], s['cr'])
            c.imp([k1, triv1], -s['cv'])
            c.imp([k1, -triv1], s['p0'])
            c.imp_eq([k1, -triv1], s['pn'], c.ITE(a, e0, v1))
            # identical resolved inputs
            ke = c.AND(pre + [-c0, -c1, sm])
            same_lit = c.EQV(c.XOR(n0, e0), c.XOR(n1_, e1))
            andpass = c.AND([a, same_lit])
            c.imp([ke, andpass], s['p0'])
            c.imp_eq([ke, andpass], s['pn'], e0)
            c.imp([ke, -andpass], s['cr'])
            c.imp_eq([ke, -andpass], s['cv'], c.AND([-a, c.XOR(n0, n1_)]))
            # otherwise alive
            kal = c.AND(pre + [-c0, -c1, -sm])
            c.imp([kal], s['al'])
        # ---------------- output tracking
        self.isout = {}
        oa = {}
        for o in I.gslots:
            if o in Eset:
                oa[o] = {w: c.AND([I.outsel[o], rt[o][w]]) for w in range(N)}
        for w in range(N):
            terms = [oa[o][w] for o in oa]
            if w not in Eset and w in I.outsel:
                terms.append(I.outsel[w])
            self.isout[w] = c.OR(terms)
        self.vac = c.OR([c.AND([I.outsel[o], rc[o]]) for o in E])
        # ---------------- backward pass: final-alive readers and out-degrees
        falive = {}
        for g in I.gslots:
            if g in Eset:
                falive[g] = c.AND([I.full[g], st[g]['al'], -st[g]['n1']])
            else:
                falive[g] = I.full[g]
        self.falive = falive
        self.oge = {}
        for v in range(N):
            rd = []
            for g in I.gslots:
                for j in (0, 1):
                    rd.append(c.AND([ct[(g, j)][v], falive[g]]))
            ext = [I.ext_ge[v][k] for k in range(1, cap + 1)]
            if v in subst:
                ext = [c.AND([e]) for e in ext]
            self.oge[v] = c.counter(rd + ext, cap + 2)
        # Transformation 1 (not frozen gates)
        for u in E:
            s = st[u]
            if prev is not None:
                ps = prev.st[u]
                frozen = c.OR([ps['cr'], ps['p0'], ps['p1'], ps['n1']])
                c.imp_eq([frozen], s['n1'], ps['n1'])
            else:
                frozen = FALSE
            cond = c.AND([I.isg[u], s['al'], -self.isout[u], -self.oge[u][1]])
            c.imp_eq([-frozen], s['n1'], cond)
        self.fremoved = {u: c.OR([st[u]['cr'], st[u]['p0'], st[u]['p1']]) for u in E}
        self.removed = {u: c.OR([self.fremoved[u], st[u]['n1']]) for u in E}
        self.cr = {u: st[u]['cr'] for u in E}
        # ---------------- protection after this step
        self.prot = {}
        p_prev = (lambda v: I.prot[v]) if prev is None else (lambda v: prev.prot[v])
        for v in I.vslots:
            pv = p_prev(v)
            if v == x and kind == 'const':
                self.prot[v] = FALSE
                continue
            cleared = FALSE
            if kind == 'const' and x in I.prot and (x, v) in I.pt:
                cleared = c.AND([p_prev(x), I.pt[(x, v)]])
            newp = FALSE
            if kind == 'quadratic' and src is not None and (src, 0) in I.inp:
                newp = c.OR([I.inp[(src, j)].get(v, FALSE) for j in (0, 1)])
            self.prot[v] = c.OR([c.AND([pv, -cleared]), newp])
        # ---------------- troubled after
        q2a = {v: c.AND([I.isv[v], self.oge[v][2], -self.oge[v][3]]) for v in range(N)}
        self.ta = {}
        for g in I.gslots:
            ins = []
            for j in (0, 1):
                r = c.new()
                for w in range(N):
                    c.imp_eq([ct[(g, j)][w]], r, q2a[w])
                c.add([-self.cc[(g, j)], -r])
                c.add([I.full[g], -r])
                ins.append(r)
            self.ta[g] = c.AND([falive[g], I.isand[g], self.oge[g][1], -self.oge[g][2],
                                -self.isout[g], -self.sm[g]] + ins)
        self.cval, self.cneg = cval, cneg
