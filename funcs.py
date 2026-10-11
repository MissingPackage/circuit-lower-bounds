"""Target function definitions -> list of truth tables (one per output).
Truth table = list of 2^n bits; row t assigns x_{i+1} = (t >> i) & 1."""
from math import ceil, log2

def _tt(n, g):
    return [int(bool(g([(t >> i) & 1 for i in range(n)]))) for t in range(1 << n)]

def build(name):
    """returns (n, [tt_out0, tt_out1, ...])"""
    p = name.split('_')
    kind = p[0]
    if kind == 'XOR':
        n = int(p[1]); return n, [_tt(n, lambda x: sum(x) % 2)]
    if kind == 'AND':
        n = int(p[1]); return n, [_tt(n, all)]
    if kind == 'MAJ':
        n = int(p[1]); return n, [_tt(n, lambda x: 2 * sum(x) > n)]
    if kind == 'MUX':  # x1 ? x2 : x3
        return 3, [_tt(3, lambda x: x[1] if x[0] else x[2])]
    if kind == 'MOD3':
        n, r = int(p[1]), int(p[2]); return n, [_tt(n, lambda x: sum(x) % 3 == r)]
    if kind.startswith('THR'):
        k, n = int(kind[3:]), int(p[1]); return n, [_tt(n, lambda x: sum(x) >= k)]
    if kind == 'SUM':  # binary representation of x1+...+xn, LSB first
        n = int(p[1]); m = ceil(log2(n + 1))
        return n, [_tt(n, lambda x, b=b: (sum(x) >> b) & 1) for b in range(m)]
    if kind == 'TT':   # TT_<n>_<integer truth table, bit t = value on row t>
        n, v = int(p[1]), int(p[2]); return n, [[(v >> t) & 1 for t in range(1 << n)]]
    raise ValueError(name)
