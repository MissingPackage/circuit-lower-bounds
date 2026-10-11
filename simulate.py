"""Independent checker: evaluates a decoded circuit row by row. Shares no code with encoder.py."""

def check(circ, target_tts):
    n = circ['n']
    for t in range(1 << n):
        v = [(t >> i) & 1 for i in range(n)]
        for j, k, f in circ['gates']:
            assert j < k < len(v)
            v.append(f[2 * v[j] + v[k]])
        for o, tt in enumerate(target_tts):
            if v[circ['outputs'][o]] != tt[t]:
                return False
    return True
