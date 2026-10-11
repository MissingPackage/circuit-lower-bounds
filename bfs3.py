"""Exhaustive enumeration of circuits over B2 on 3 inputs. Independent of encoder.py/simulate.py/funcs.py.
A circuit with g gates is identified with the set of functions sitting on its nodes (3 inputs + g gates);
level g holds every such set reachable with g gates. cost[f] = first level at which f sits on some node.
Truth tables are 8-bit integers. All 16 two-input operations are applied to every pair of nodes."""
import csv, sys, time

X = [0b10101010, 0b11001100, 0b11110000]   # x1, x2, x3 ; bit t = value on row t

def ops(a, b):
    na, nb = a ^ 255, b ^ 255
    m = (na & nb, na & b, a & nb, a & b)      # minterms 00,01,10,11
    res = set()
    for code in range(16):
        r = 0
        for i in range(4):
            if code >> i & 1:
                r |= m[i]
        res.add(r)
    return res

def main(out):
    t0 = time.time()
    cost = {f: 0 for f in X}
    level = {frozenset(X)}
    g = 0
    while len(cost) < 256:
        g += 1
        nxt = set()
        for st in level:
            nodes = sorted(st)
            new = set()
            for i in range(len(nodes)):
                for j in range(i + 1, len(nodes)):
                    new |= ops(nodes[i], nodes[j])
            new -= st
            for f in new:
                if f not in cost:
                    cost[f] = g
                nxt.add(st | {f})
        print(f'gates={g} circuits(sets)={len(nxt)} functions_found={len(cost)} t={time.time()-t0:.1f}s', flush=True)
        level = nxt
    with open(out, 'w', newline='') as fh:
        w = csv.writer(fh); w.writerow(['tt', 'bfs_min'])
        for f in range(256):
            w.writerow([f, cost[f]])
    hist = {}
    for f in range(256):
        hist[cost[f]] = hist.get(cost[f], 0) + 1
    print('histogram cost->count', sorted(hist.items()))

if __name__ == '__main__':
    main(sys.argv[1])
