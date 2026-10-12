import sys
def topologies(k, s):
    """all gate-pair lists (a<b<i) on inputs 0..k-1, gates k..k+s-1, every non-output node used,
    inputs in first-use order (unordered pairs)."""
    n = k + s
    out = []
    pairs = []
    deg = [0]*n
    def rec(i, nxt):
        if i == n:
            if all(deg[v] >= 1 for v in range(n-1)):
                out.append(tuple(pairs))
            return
        # prune: unused nodes among 0..i-1 must be coverable by remaining 2*(n-i) edge slots
        unused = sum(1 for v in range(i) if deg[v] == 0) + (k - nxt)  # unused inputs not yet introduced
        unused = sum(1 for v in range(k, i) if deg[v] == 0) + sum(1 for v in range(nxt) if deg[v]==0) + (k - nxt)
        if unused > 2*(n - i):
            return
        cands = list(range(nxt)) + [v for v in (nxt, nxt+1) if v < k] + list(range(k, i))
        for ia in range(len(cands)):
            a = cands[ia]
            for b in cands[ia+1:]:
                # first-use ordering
                new = [v for v in (a, b) if v < k and v >= nxt]
                if new and new != list(range(nxt, nxt+len(new))):
                    continue
                pairs.append((a, b)); deg[a] += 1; deg[b] += 1
                rec(i+1, nxt + len(new))
                pairs.pop(); deg[a] -= 1; deg[b] -= 1
    rec(k, 0)
    return out
if __name__ == '__main__':
    k, s = int(sys.argv[1]), int(sys.argv[2])
    T = topologies(k, s)
    print(k, s, len(T))
