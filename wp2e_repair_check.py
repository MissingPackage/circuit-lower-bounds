"""WP2e: mechanical check of the functional identity behind the Theorem 1 / Section 3.2 repair
(pre-registration Section 5).  It checks h(x) == h|rho(wire(x)) for h = f <> g; it does NOT check gate
counts (those are the hand argument in the README WP2e section).

h = f <> g: n blocks of k = 3 variables, block b feeds g(x_b1, x_b2, x_b3) into input b of f.
A 1-substitution replaces x_bp by rho(z), z = all other 3n - 1 variables (rho arbitrary).
Repair (GHKK Theorem 1 proof, PDF p.9): with G = g(x_b1, x_b2, x_b3) computed on the original inputs,
every other position q of block b receives G xor tau_0(q) if tau_0(q) != tau_1(q), else the constant
tau_0(q), where tau_0, tau_1 are the checker's (wp2e_weak1) witnesses for Y = {p}.  All other variables
are passed unchanged.

Gadgets: MUX_3 (x1 ? x2 : x3) and MAJ_3.  Cases: n = 1 with all 4 functions f in B_1 and all 16 rho
of the 2 remaining variables, every position; n = 2 with all 16 f in B_2, both blocks, every position,
2000 random rho (truth tables on 5 variables, seeded) per (f, block, position).
"""
import sys, random, itertools
import wp2e_weak1

GADGETS = {'MUX_3': lambda x: x[1] if x[0] else x[2], 'MAJ_3': lambda x: int(x[0] + x[1] + x[2] >= 2)}


def wiring(gtt, p):
    w = wp2e_weak1.weak1_witnesses(gtt, 3)
    t0, t1 = w[(p,)]
    rule = {}
    for q in t0:
        rule[q] = ('G', t0[q]) if t0[q] != t1[q] else ('const', t0[q])
    return rule


def run(name, g, n, fs, rhos_for, label):
    gtt = wp2e_weak1.tt_of(3, g)
    N = 3 * n
    fails = checks = 0
    for b in range(n):
        for p in range(3):
            rule = wiring(gtt, p)
            sub = 3 * b + p
            others = [v for v in range(N) if v != sub]
            for fi, f in enumerate(fs):
                for rho in rhos_for(N - 1, fi, b, p):
                    def h(x):
                        return f([g(x[3 * i:3 * i + 3]) for i in range(n)])

                    def h_rho(z):          # z: values of the variables in `others`
                        x = [0] * N
                        for v, val in zip(others, z):
                            x[v] = val
                        zi = sum(val << i for i, val in enumerate(z))
                        x[sub] = (rho >> zi) & 1
                        return h(x)
                    for xt in range(1 << N):
                        x = [(xt >> i) & 1 for i in range(N)]
                        G = g(x[3 * b:3 * b + 3])
                        xw = list(x)
                        for q, (kind, c) in rule.items():
                            xw[3 * b + q] = (G ^ c) if kind == 'G' else c
                        z = [xw[v] for v in others]
                        checks += 1
                        if h_rho(z) != h(x):
                            fails += 1
    print(f'{label} gadget={name} n={n} wirings={[wiring(gtt, p) for p in range(3)]} checks={checks} failures={fails}')
    return fails


def main():
    rnd = random.Random(20261012)
    total = 0
    f1 = [lambda y, c=c: c[y[0]] for c in itertools.product((0, 1), repeat=2)]
    f2 = [lambda y, c=c: c[2 * y[0] + y[1]] for c in itertools.product((0, 1), repeat=4)]
    for name, g in GADGETS.items():
        total += run(name, g, 1, f1, lambda m, fi, b, p: range(1 << (1 << m)), 'n=1 all rho')
        total += run(name, g, 2, f2, lambda m, fi, b, p: [rnd.getrandbits(1 << m) for _ in range(2000)],
                     'n=2 random rho')
    print('repair_check', 'PASS' if total == 0 else f'FAIL ({total} failures)')
    return 0 if total == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
