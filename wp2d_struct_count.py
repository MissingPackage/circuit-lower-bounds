"""Quick structure counter (no gate types): k inputs all used, s gates, every node in the output cone,
first-use input ordering, adjacent independent gates in non-decreasing (a,b) order."""
import sys, time


def candidates(k, n, u):
    avail = list(range(u)) + list(range(k, n))
    c = []
    for x in range(len(avail)):
        for y in range(x + 1, len(avail)):
            c.append((avail[x], avail[y]))
    if u < k:
        for a in range(u):
            c.append((a, u))
        for b in range(k, n):
            c.append((u, b))
        if u + 1 < k:
            c.append((u, u + 1))
    return c


def count(k, s):
    outdeg = [0] * (k + s)
    pairs = [None] * s
    total = 0

    def rec(i, u, D):
        nonlocal total
        r = s - i - 1
        n = k + i
        prev = pairs[i - 1] if i else None
        prev_node = n - 1
        for a, b in candidates(k, n, u):
            D2 = D - (outdeg[a] == 0) - (outdeg[b] == 0) + 1
            if D2 > r + 1:
                continue
            if r == 0 and D2 != 1:
                continue
            if i and prev_node not in (a, b) and (a, b) < prev:
                continue
            u2 = u + (a == u) + (b == u) + (b == u + 1 and a == u)
            outdeg[a] += 1; outdeg[b] += 1
            pairs[i] = (a, b)
            if r == 0:
                total += 1
            else:
                rec(i + 1, u2, D2)
            outdeg[a] -= 1; outdeg[b] -= 1

    rec(0, 0, k)
    return total


if __name__ == '__main__':
    for ks in sys.argv[1:]:
        k, s = map(int, ks.split(','))
        t0 = time.time()
        c = count(k, s)
        print(f'k={k} s={s} structures={c} t={time.time()-t0:.1f}s', flush=True)
