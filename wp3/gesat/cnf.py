"""Small CNF builder with constant folding, Tseitin gates and exact unary counters (WP3.2)."""

TRUE = 1
FALSE = -1


class CNF:
    def __init__(self):
        self.n = 1                 # variable 1 is the constant TRUE
        self.clauses = [[1]]

    def new(self):
        self.n += 1
        return self.n

    def add(self, clause):
        out = []
        for l in clause:
            if l == TRUE:
                return
            if l == FALSE:
                continue
            out.append(l)
        self.clauses.append(out)

    # ------------------------------------------------------------ gates
    def AND(self, lits):
        ls = []
        for l in lits:
            if l == FALSE:
                return FALSE
            if l == TRUE:
                continue
            ls.append(l)
        ls = list(dict.fromkeys(ls))
        if any(-l in ls for l in ls):
            return FALSE
        if not ls:
            return TRUE
        if len(ls) == 1:
            return ls[0]
        v = self.new()
        for l in ls:
            self.clauses.append([-v, l])
        self.clauses.append([v] + [-l for l in ls])
        return v

    def OR(self, lits):
        return -self.AND([-l for l in lits])

    def XOR(self, a, b):
        if a == FALSE:
            return b
        if b == FALSE:
            return a
        if a == TRUE:
            return -b
        if b == TRUE:
            return -a
        if a == b:
            return FALSE
        if a == -b:
            return TRUE
        v = self.new()
        self.clauses += [[-v, a, b], [-v, -a, -b], [v, -a, b], [v, a, -b]]
        return v

    def EQV(self, a, b):
        return -self.XOR(a, b)

    def ITE(self, c, a, b):
        return self.OR([self.AND([c, a]), self.AND([-c, b])])

    def imp(self, prem, concl):
        """AND(prem) -> concl (concl a literal)."""
        self.add([-p for p in prem] + [concl])

    def imp_eq(self, prem, a, b):
        """AND(prem) -> (a <-> b)."""
        self.add([-p for p in prem] + [-a, b])
        self.add([-p for p in prem] + [a, -b])

    def amo(self, lits):
        lits = [l for l in lits if l != FALSE]
        if len(lits) <= 1:
            return
        if len(lits) <= 5:
            for i in range(len(lits)):
                for j in range(i + 1, len(lits)):
                    self.add([-lits[i], -lits[j]])
            return
        prev = None
        for i, x in enumerate(lits):
            if i == len(lits) - 1:
                if prev is not None:
                    self.add([-prev, -x])
                break
            r = self.new()
            self.add([-x, r])
            if prev is not None:
                self.add([-prev, r])
                self.add([-prev, -x])
            prev = r

    def counter(self, lits, K):
        """Exact sequential counter: returns ge[0..K] with ge[k] <-> (sum >= k);
        ge[0] = TRUE. Duplicated literals are allowed."""
        prev = [TRUE] + [FALSE] * K
        for x in lits:
            if x == FALSE:
                continue
            cur = [TRUE]
            for k in range(1, K + 1):
                cur.append(self.OR([prev[k], self.AND([prev[k - 1], x])]))
            prev = cur
        return prev

    def geq_diff(self, pos, neg, K):
        """literal for  sum(pos) - sum(neg) >= K  (exact)."""
        neg = [l for l in neg if l != FALSE]
        T = K + len(neg)
        if T <= 0:
            return TRUE
        lits = list(pos) + [-l for l in neg]
        if T > len([l for l in lits if l != FALSE]):
            return FALSE
        ge = self.counter(lits, T)
        return ge[T]

    def lex_geq(self, a, b):
        """Constraint: bit vector a >=lex b (1 > 0), a[0] most significant."""
        eq_prefix = TRUE
        for x, y in zip(a, b):
            # if prefix equal then x >= y
            self.add([-eq_prefix, x, -y])
            eq_prefix = self.AND([eq_prefix, self.EQV(x, y)])
