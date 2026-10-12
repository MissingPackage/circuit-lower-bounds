import sys, os, itertools, time
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/claude/progetti/circuit-lower-bounds')
import numpy as np
import stable_check as sc
from topo import topologies

OPS = ['and', 'andnot', 'notand', 'or', 'xor']   # normal non-degenerate B2 ops
OPF = {'and': [0,0,0,1], 'andnot': [0,0,1,0], 'notand': [0,1,0,0], 'or': [0,1,1,1], 'xor': [0,1,1,0]}  # f[a*2+b]

def var_tt(k, i):
    return np.uint64(sc.var_mask(k, i))

def all_tts(k, s):
    full = np.uint64((1 << (1 << k)) - 1)
    res = []
    T = topologies(k, s)
    for pairs in T:
        vals = [np.array([var_tt(k, i)], dtype=np.uint64) for i in range(k)]
        # vals[j] has shape (5^g,) after g gates; earlier arrays broadcast by repeat
        cur = 1
        for (a, b) in pairs:
            A = np.repeat(vals[a], cur // len(vals[a])) if len(vals[a]) != cur else vals[a]
            B = np.repeat(vals[b], cur // len(vals[b])) if len(vals[b]) != cur else vals[b]
            nA = ~A & full; nB = ~B & full
            new = np.concatenate([A & B, A & nB, nA & B, A | B, A ^ B])  # op index = block
            # extend all previous arrays to 5*cur by tiling (block structure: op is the slowest index)
            vals = [np.tile(v if len(v) == cur else np.repeat(v, cur // len(v)), 5) for v in vals]
            cur *= 5
            vals.append(new)
        res.append(vals[-1])
    return T, np.unique(np.concatenate(res))

def stable_vec(tts, k, variant):
    tests = sc.tests_for(variant, k)
    ok = np.ones(len(tts), dtype=bool)
    for alts in tests:
        anyok = np.zeros(len(tts), dtype=bool)
        idx = np.nonzero(ok)[0]
        sub = tts[idx]
        for M, P in alts:
            anyok[idx] |= (sub & np.uint64(M)) == np.uint64(P)
        ok &= anyok
        if not ok.any():
            break
    return ok
