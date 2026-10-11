"""Glue for apgoucher/optimal5 (Knuth's optimal 5-input chains), WP2b.  Pure Python: this host has no C++
compiler, so knuthies.dat is decoded directly (mirror of bytes2gv() in optimal5.h) instead of building
human_readable.cpp.  Nothing from optimal5 is copied into the repository; the file is read from OPT5_DIR.

Conventions (see wp2b_preregistration_2026-10-11.txt):
  WP1 integer  : bit t = f on row t, row t assigns x_{i+1} = (t >> i) & 1.
  optimal5 int : bit b = f on the assignment x_j = 1 - ((b >> (5 - j)) & 1)   (x1 = 0x0000ffff, ...).
Record format : 15 bytes = 3 little-endian 40-bit words = 12 ten-bit gate codes g; g == 0 terminates;
                op = g >> 8 in {0:'&', 1:'|', 2:'^', 3:'&~'}, operands calcs[(g & 15) + 1], calcs[((g >> 4) & 15) + 1]
                with calcs = [0, x1, x2, x3, x4, x5, gate6, gate7, ...].  The key of a record is the truth
                table (optimal5 convention) of its last gate = the canonical (minimum) NPN representative.
"""
import os, itertools, random

OPT5_DIR = os.environ.get('OPT5_DIR', '/tmp/optimal5')
OPT5_COMMIT = 'b7668d77d7e57d504c19e4cf4884d9e2d0991d88'
N_RECORDS = 616124
INPUTS_OPT5 = [0x0000ffff, 0x00ff00ff, 0x0f0f0f0f, 0x33333333, 0x55555555]
OPS = ['&', '|', '^', '&~']
M32 = 0xffffffff
K = 5
R = 32

# index maps between the two conventions: WP1 row t  <->  optimal5 bit B_OF_T[t]
B_OF_T = [sum((1 - ((t >> (j - 1)) & 1)) << (5 - j) for j in range(1, 6)) for t in range(R)]
T_OF_B = [0] * R
for _t, _b in enumerate(B_OF_T):
    T_OF_B[_b] = _t
assert sorted(B_OF_T) == list(range(R))


def opt5_to_wp1(w):
    return sum(((w >> B_OF_T[t]) & 1) << t for t in range(R))


def wp1_to_opt5(v):
    return sum(((v >> T_OF_B[b]) & 1) << b for b in range(R))


# ---------------------------------------------------------------- records
def load_records(path=None):
    """list of gate lists [(op, i1, i2), ...] in file order (op index into OPS, i1/i2 calcs indices 1..16)"""
    path = path or os.path.join(OPT5_DIR, 'knuthies.dat')
    data = open(path, 'rb').read()
    assert len(data) == N_RECORDS * 15, len(data)
    recs = []
    for j in range(0, len(data), 15):
        codes = []
        for i in range(3):
            x = int.from_bytes(data[j + 5 * i:j + 5 * i + 5], 'little')
            codes += [(x >> (10 * q)) & 1023 for q in range(4)]
        n = 12
        for i, g in enumerate(codes):
            if g == 0:
                n = i
                break
        assert all(g == 0 for g in codes[n:]), ('garbage after terminator', j // 15, codes)
        recs.append([(g >> 8, (g & 15) + 1, ((g >> 4) & 15) + 1) for g in codes[:n]])
    return recs


def chain_tt_opt5(gates):
    calcs = [0] + INPUTS_OPT5
    for op, i1, i2 in gates:
        a, b = calcs[i1], calcs[i2]
        calcs.append([a & b, a | b, a ^ b, a & ~b & M32][op])
    return calcs[-1]


def chain_text(gates, outneg=False):
    s = []
    for i, (op, i1, i2) in enumerate(gates):
        s.append('x%d = x%d %s x%d' % (i + 6, i1, OPS[op], i2))
    s.append('result = %sx%d' % ('~' if outneg else '', len(gates) + 5 if gates else 1))
    return '; '.join(s)


GATE_TABLE = {0: [0, 0, 0, 1], 1: [0, 1, 1, 1], 2: [0, 1, 1, 0], 3: [0, 0, 1, 0]}


def chain_to_wp1_circuit(gates):
    """WP1 JSON circuit {n, gates:[[j,k,[f00,f01,f10,f11]],...], outputs:[v]} computing the SAME function of
    (x1..x5) as the chain: input x_j is node j-1, gate calcs[c] is node c-1."""
    out = []
    for op, i1, i2 in gates:
        j, k = i1 - 1, i2 - 1
        f = list(GATE_TABLE[op])
        assert j != k
        if j > k:
            j, k = k, j
            f = [f[0], f[2], f[1], f[3]]
        out.append([j, k, f])
    return dict(n=K, gates=out, outputs=[len(gates) + 4 if gates else 0])


# ---------------------------------------------------------------- NPN transformations (WP1 convention)
PERMS = list(itertools.permutations(range(K)))
# SIGMA[(perm, neg)][a] = row index a' such that g(a) = f(a') for g(x) = f(sigma(x)), sigma(x)_j = x_{perm[j]} ^ neg_j
SIGMA = {}
for _p in PERMS:
    for _n in range(1 << K):
        SIGMA[_p, _n] = [sum((((a >> _p[j]) & 1) ^ ((_n >> j) & 1)) << j for j in range(K)) for a in range(R)]


def transform_wp1(tt, perm, neg, out):
    """NPN image of the WP1 integer tt: g(x) = f(x_{perm[0]}^neg_0, ..., x_{perm[4]}^neg_4) ^ out"""
    s = SIGMA[tuple(perm), neg]
    g = sum(((tt >> s[a]) & 1) << a for a in range(R))
    return g ^ (M32 if out else 0)


def orbit_opt5(tt_wp1):
    """dict optimal5-integer -> (perm, neg, out) over the whole NPN orbit (one witness per image)"""
    f = [(tt_wp1 >> a) & 1 for a in range(R)]
    orb = {}
    for key, s in SIGMA.items():
        w = 0
        for a in range(R):
            if f[s[a]]:
                w |= 1 << B_OF_T[a]
        orb.setdefault(w, key + (0,))
        orb.setdefault(w ^ M32, key + (1,))
    return orb


def transform_circuit(circ, perm, neg, out):
    """circuit computing g(x) = f(sigma(x)) ^ out from a circuit computing f (WP1 JSON), no extra gates:
    input node j of f becomes literal x_{perm[j]} ^ neg_j, negations are absorbed into the reading gates."""
    n = circ['n']
    gates = []
    for j, k, f in circ['gates']:
        f = list(f)
        if j < n and (neg >> j) & 1:
            f = [f[2], f[3], f[0], f[1]]
        if k < n and (neg >> k) & 1:
            f = [f[1], f[0], f[3], f[2]]
        j2 = perm[j] if j < n else j
        k2 = perm[k] if k < n else k
        if j2 > k2:
            j2, k2 = k2, j2
            f = [f[0], f[2], f[1], f[3]]
        gates.append([j2, k2, f])
    o = circ['outputs'][0]
    if o < n:
        assert not out and not (neg >> o) & 1, 'literal output with negation cannot be expressed without a gate'
        o = perm[o]
    elif out:
        gates[o - n][2] = [b ^ 1 for b in gates[o - n][2]]
    return dict(n=n, gates=gates, outputs=[o])


# ---------------------------------------------------------------- packed (bit-sliced) helpers
def rep_mask(m, n, slot):
    """integer with the `slot`-bit pattern m replicated n times"""
    return int.from_bytes(m.to_bytes(slot // 8, 'little') * n, 'little')


def pack(words, slot):
    return int.from_bytes(b''.join(w.to_bytes(slot // 8, 'little') for w in words), 'little')


def unpack_lsb(x, n, slot):
    """bit 0 of every slot as a list of ints"""
    return [b & 1 for b in x.to_bytes(n * slot // 8, 'little')[0::slot // 8]]


def nonzero_slots(z):
    """bit 0 of each slot = 1 iff the 32-bit word in the slot is nonzero (slot width >= 32)"""
    z |= z >> 16
    z |= z >> 8
    z |= z >> 4
    z |= z >> 2
    z |= z >> 1
    return z


class Packed:
    """NPN moves on n words packed in slots; index bit q of the 32-bit word (stride 2^q) is an input."""

    def __init__(self, n, slot):
        self.n, self.slot = n, slot
        self.ONE = rep_mask(1, n, slot)
        self.W = rep_mask(M32, n, slot)
        self.SET = [rep_mask(sum(1 << b for b in range(R) if (b >> q) & 1), n, slot) for q in range(K)]
        self.CLR = [rep_mask(sum(1 << b for b in range(R) if not (b >> q) & 1), n, slot) for q in range(K)]
        self.TM = {}
        for p in range(K):
            for q in range(p + 1, K):
                self.TM[p, q] = rep_mask(sum(1 << b for b in range(R) if (b >> p) & 1 and not (b >> q) & 1), n, slot)

    def negate(self, P, q):
        s = 1 << q
        return ((P & self.SET[q]) >> s) | ((P & self.CLR[q]) << s)

    def swap(self, P, p, q):
        if p > q:
            p, q = q, p
        sh = (1 << q) - (1 << p)
        d = (P ^ (P >> sh)) & self.TM[p, q]
        return P ^ d ^ (d << sh)

    def permute(self, P, perm):
        cur = list(range(K))
        for i in range(K):
            j = cur.index(perm[i])
            if j != i:
                P = self.swap(P, i, j)
                cur[i], cur[j] = cur[j], cur[i]
        return P

    def equal(self, P, Q):
        """ONE-bit per slot: 1 iff P == Q in that slot"""
        return nonzero_slots(P ^ Q) & self.ONE ^ self.ONE

    def walk(self, Q):
        """yields the 3840 input-transform images of Q (perm, Gray-coded negations)"""
        for perm in PERMS:
            P = self.permute(Q, perm)
            yield P
            for i in range(1, 1 << K):
                q = (i & -i).bit_length() - 1
                P = self.negate(P, q)
                yield P


def single_word_images(w):
    """all 3840 input-transform images of one 32-bit word (optimal5 index convention), via Packed(1, 32)"""
    pk = Packed(1, 32)
    return list(pk.walk(w))


def self_test():
    # conversion is a bijection and inverse
    rnd = random.Random(1)
    for _ in range(200):
        v = rnd.getrandbits(32)
        assert opt5_to_wp1(wp1_to_opt5(v)) == v and wp1_to_opt5(opt5_to_wp1(v)) == v
    # x_j in optimal5 convention is INPUTS_OPT5[j-1]; in WP1 convention it is the var mask
    for j in range(1, 6):
        wp1 = sum(1 << t for t in range(R) if (t >> (j - 1)) & 1)
        assert opt5_to_wp1(INPUTS_OPT5[j - 1]) == wp1, j
    # packed moves agree with the row-level transform on random words (WP1 index convention: input x_{q+1} = index bit q)
    pk = Packed(3, 32)
    for _ in range(100):
        ws = [rnd.getrandbits(32) for _ in range(3)]
        P = pack(ws, 32)
        q = rnd.randrange(K)
        got = pk.negate(P, q)
        want = pack([transform_wp1(w, list(range(K)), 1 << q, 0) for w in ws], 32)
        assert got == want
        p, q = rnd.sample(range(K), 2)
        perm = list(range(K)); perm[p], perm[q] = q, p
        assert pk.swap(P, p, q) == pack([transform_wp1(w, perm, 0, 0) for w in ws], 32)
        perm = list(rnd.sample(range(K), K))
        inv = [perm.index(i) for i in range(K)]     # permute() composes the selection-sort transpositions, giving perm^-1
        assert pk.permute(P, perm) == pack([transform_wp1(w, inv, 0, 0) for w in ws], 32)
    # the walk visits 3840 distinct images of a word with trivial stabiliser and matches the orbit function;
    # 0x169ae443 (README example) has a stabiliser of order 4: 960 input images, orbit 1920
    for w, n_img, n_orb in ((0x9f767c45, 3840, 7680), (0x169ae443, 960, 1920)):
        imgs = single_word_images(w)
        assert len(imgs) == 3840 and len(set(imgs)) == n_img, len(set(imgs))
        orb = orbit_opt5(opt5_to_wp1(w))
        assert set(imgs) | {x ^ M32 for x in imgs} == set(orb) and len(orb) == n_orb
    # transform_circuit agrees with transform_wp1 on a random circuit
    import stable_check
    for _ in range(50):
        gates = []
        for i in range(8):
            j, k = sorted(rnd.sample(range(K + i), 2))
            gates.append([j, k, [rnd.randrange(2) for _ in range(4)]])
        circ = dict(n=K, gates=gates, outputs=[K + 7])
        tt = stable_check.circuit_tt(circ)
        perm = list(rnd.sample(range(K), K)); neg = rnd.getrandbits(K); out = rnd.randrange(2)
        c2 = transform_circuit(circ, perm, neg, out)
        assert stable_check.circuit_tt(c2) == transform_wp1(tt, perm, neg, out)
    return True


if __name__ == '__main__':
    print('self_test', self_test())
