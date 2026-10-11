"""SAT encoding of: "there is a circuit with exactly s gates over B2 computing the given outputs".
Nodes 0..n-1 = inputs, n..n+s-1 = gates. Each gate picks an ordered pair j<k of earlier nodes and a
2-input truth table. Outputs may be any node (input or gate).

mode 'none' : plain encoding, all 16 gate types, no symmetry breaking.
mode 'full' : symmetry breaking:
   N  normal gates (g(0,0)=0); a target with f(0)=1 is replaced by its complement and must then sit on a GATE
      (the complement is absorbed into that gate when the circuit is decoded);
   D  no degenerate gates (constant / projection), switched off when some output is a constant or a negated input;
   U  every gate is an output or feeds a later gate;
   O  consecutive gates i,i+1: i feeds i+1, or pair(i) <= pair(i+1) in colex order;
   S  (only if sym=True) x_p is first used no later than x_{p+1}  (valid for input-symmetric targets).
   With U the encoding is NOT monotone in s: exact values need UNSAT for every s' < s.

WP2 extension (free-function search): if `outs` is an integer q, the circuit has q outputs whose truth
tables are NOT fixed but are variables self.fv[o, t] (one per output and row); constraints on the function
(e.g. stability, see stability.py) are added on those variables.  In mode 'full' (normal gates) an output
node computes fv XOR sgn[o]; with sgnfree=False sgn[o] is fixed to 0 (WLOG only when the searched property
is invariant under complement), with sgnfree=True sgn[o] is a variable and a complemented output must sit
on a gate (absorbed at decode time, as for fixed targets with f(0)=1).  The free path assumes the searched
function is neither a constant nor a literal (constraint D stays on).  With a fixed `outs` list the
encoding is unchanged from WP1 (regression-checked: identical variables and clauses).
"""
from itertools import combinations


class Enc:
    def __init__(self, n, outs, s, mode='full', sym=False, sgnfree=False):
        self.n, self.s, self.mode = n, s, mode
        self.R = 1 << n
        self.nv = 0
        self.cl = []
        N = n + s
        normal = mode != 'none'
        inputs = [[(t >> i) & 1 for t in range(self.R)] for i in range(n)]
        self.free = isinstance(outs, int)
        self.fv = {}    # (o,t) -> var   (free outputs only)
        self.sgn = {}   # o -> var       (free outputs, normal mode, sgnfree)
        if self.free:
            self.outs = [None] * outs
            self.neg = [False] * outs
            tg = [None] * outs
            nondeg = normal
            for o in range(outs):
                for t in range(self.R):
                    self.fv[o, t] = self._new()
                if normal and sgnfree:
                    self.sgn[o] = self._new()
        else:
            self.outs = [list(o) for o in outs]
            # normalised targets
            self.neg = [normal and o[0] == 1 for o in self.outs]
            tg = [[b ^ 1 for b in o] if ng else o for o, ng in zip(self.outs, self.neg)]

            def trivial(o):
                if len(set(o)) == 1:
                    return True
                return any(o == [b ^ 1 for b in x] for x in inputs)
            nondeg = normal and not any(trivial(o) for o in self.outs)

        self.sel = {}   # (i,j,k) -> var
        self.op = {}    # (i,a,b) -> var
        self.val = {}   # (i,t)   -> var
        self.out = {}   # (o,node)-> var
        for i in range(n, N):
            for j, k in combinations(range(i), 2):
                self.sel[i, j, k] = self._new()
            for a in (0, 1):
                for b in (0, 1):
                    if normal and a == 0 and b == 0:
                        continue
                    self.op[i, a, b] = self._new()
            for t in range(self.R):
                if normal and t == 0:
                    continue
                self.val[i, t] = self._new()
        for o in range(len(tg)):
            for v in range(N):
                self.out[o, v] = self._new()

        def vlit(v, t, want):
            """literal true iff node v has value `want` on row t; returns True/False if constant."""
            if v < n:
                return inputs[v][t] == want
            if normal and t == 0:
                return want == 0
            x = self.val[v, t]
            return x if want else -x

        def oplit(i, a, b, want):
            if normal and a == 0 and b == 0:
                return want == 0
            x = self.op[i, a, b]
            return x if want else -x

        def add(lits):
            c = []
            for l in lits:
                if l is True:
                    return
                if l is False:
                    continue
                c.append(l)
            self.cl.append(c)

        # each gate: exactly one input pair
        for i in range(n, N):
            ps = [self.sel[i, j, k] for j, k in combinations(range(i), 2)]
            self.cl.append(ps)
            for x, y in combinations(ps, 2):
                self.cl.append([-x, -y])
        # gate semantics
        for i in range(n, N):
            for j, k in combinations(range(i), 2):
                sv = self.sel[i, j, k]
                for t in range(self.R):
                    for a in (0, 1):
                        for b in (0, 1):
                            la, lb = vlit(j, t, a), vlit(k, t, b)
                            if la is False or lb is False:
                                continue
                            pre = [-sv] + ([] if la is True else [-la]) + ([] if lb is True else [-lb])
                            for c in (0, 1):
                                # (sel & vj=a & vk=b & vi=c) -> op[a,b]=c
                                add(pre + [vlit(i, t, 1 - c), oplit(i, a, b, c)])
        # outputs
        for o, tt in enumerate(tg):
            ovs = [self.out[o, v] for v in range(N)]
            self.cl.append(ovs)
            for x, y in combinations(ovs, 2):
                self.cl.append([-x, -y])
            if self.free:
                sg = self.sgn.get(o)
                for v in range(N):
                    if sg is not None and v < n:
                        self.cl.append([-sg, -self.out[o, v]])   # complemented output must be a gate
                    for t in range(self.R):
                        f = self.fv[o, t]
                        for a in (0, 1):
                            la = vlit(v, t, a)
                            if la is False:
                                continue
                            pre = [-self.out[o, v]] + ([] if la is True else [-la])
                            if sg is None:          # out & node=a -> fv=a
                                self.cl.append(pre + [f if a else -f])
                            else:                   # out & node=a & sgn=g -> fv = a^g
                                for g in (0, 1):
                                    c = a ^ g
                                    self.cl.append(pre + [-sg if g else sg] + [f if c else -f])
                continue
            for v in range(N):
                if self.neg[o] and v < n:
                    self.cl.append([-self.out[o, v]]); continue
                for t in range(self.R):
                    add([-self.out[o, v], vlit(v, t, tt[t])])
        if not normal:
            return
        # D: non-degenerate normal gates: forbid (f01,f10,f11) in {000, 011, 101}
        if nondeg:
            for i in range(n, N):
                p, q, r = self.op[i, 0, 1], self.op[i, 1, 0], self.op[i, 1, 1]
                self.cl += [[p, q, r], [p, -q, -r], [-p, q, -r]]
        # U: every gate used
        for i in range(n, N):
            c = [self.out[o, i] for o in range(len(tg))]
            for i2 in range(i + 1, N):
                for j, k in combinations(range(i2), 2):
                    if i in (j, k):
                        c.append(self.sel[i2, j, k])
            self.cl.append(c)
        # O: colex ordering of consecutive independent gates
        for i in range(n, N - 1):
            for j, k in combinations(range(i), 2):
                for j2, k2 in combinations(range(i), 2):   # pairs of gate i+1 not using i
                    if (k2, j2) < (k, j):
                        self.cl.append([-self.sel[i, j, k], -self.sel[i + 1, j2, k2]])
        # S: inputs first used in index order
        if sym:
            use = {}
            for i in range(n, N):
                for p in range(n):
                    u = self._new(); use[i, p] = u
                    self.cl.append([-u] + [self.sel[i, j, k] for j, k in combinations(range(i), 2) if p in (j, k)])
            for p in range(n - 1):
                for i in range(n, N):
                    prev = [use[i2, p] for i2 in range(n, i + 1)]
                    for j, k in combinations(range(i), 2):
                        if p + 1 in (j, k):
                            self.cl.append([-self.sel[i, j, k]] + prev)

    def _new(self):
        self.nv += 1
        return self.nv

    def decode(self, model):
        """model -> real circuit over B2: dict(n, gates=[(j,k,(f00,f01,f10,f11))], outputs=[node,...])."""
        true = set(l for l in model if l > 0)
        n, s = self.n, self.s
        normal = self.mode != 'none'
        gates = []
        for i in range(n, n + s):
            jk = [(j, k) for j, k in combinations(range(i), 2) if self.sel[i, j, k] in true]
            assert len(jk) == 1
            j, k = jk[0]
            f = [0 if (normal and (a, b) == (0, 0)) else int(self.op[i, a, b] in true) for a in (0, 1) for b in (0, 1)]
            gates.append([j, k, f])
        outs = []
        for o in range(len(self.outs)):
            vs = [v for v in range(n + s) if self.out[o, v] in true]
            assert len(vs) == 1
            outs.append(vs[0])
        tts = None
        if self.free:
            # the function found by the solver; its sign is read from the model (0 when sgn is fixed)
            self.neg = [o in self.sgn and self.sgn[o] in true for o in range(len(self.outs))]
            tts = [[int(self.fv[o, t] in true) for t in range(self.R)] for o in range(len(self.outs))]
        # absorb complements of negated targets into their gates
        flip = set(v for v, ng in zip(outs, self.neg) if ng)
        keep = set(v for v, ng in zip(outs, self.neg) if not ng)
        if flip & keep:
            raise RuntimeError('a gate is both a plain and a complemented output')
        for v in sorted(flip):
            g = gates[v - n]
            g[2] = [b ^ 1 for b in g[2]]
            for g2 in gates[v - n + 1:]:
                f = g2[2]
                if g2[0] == v:   # first input complemented: swap rows a=0 <-> a=1
                    g2[2] = f = [f[2], f[3], f[0], f[1]]
                if g2[1] == v:   # second input complemented
                    g2[2] = [f[1], f[0], f[3], f[2]]
        d = dict(n=n, gates=[(j, k, tuple(f)) for j, k, f in gates], outputs=outs)
        if tts is not None:
            d['tt'] = tts
        return d
