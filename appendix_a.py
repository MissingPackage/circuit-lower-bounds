"""Port of the two scripts in GHKK, Appendix A ("Scripts for the proof of Lemma 4"), PDF p.17-18.
Script (i) checks the witness table M (20 ordered pairs, positive sign only); script (ii) checks the
11-gate circuit g1..g11 against the printed truth table.  Both are copied unchanged except for the
indentation lost by the PDF text extraction; the only additions are the prints, the exit status and the
export of the circuit in the WP1 JSON format for simulate.py.
Exit status 0 = both asserts pass on all rows; an AssertionError (exit 1) otherwise.
"""
import itertools, json, sys

# ---- script (i), verbatim ----
tt=[0,0,0,0,0,0,1,1,0,1,0,1,1,1,1,0,0,1,1,1,0,1,1,0,0,1,1,0,1,0,0,0]
M = {(0,1): (0,1,0), (0,2): (0,0,1), (0,3): (0,0,1), (0,4): (0,0,1),
     (1,0): (1,0,0), (1,2): (0,0,1), (1,3): (0,0,1), (1,4): (0,1,0),
     (2,0): (1,0,0), (2,1): (0,1,0), (2,3): (0,1,0), (2,4): (0,0,1),
     (3,0): (0,1,0), (3,1): (1,0,0), (3,2): (1,0,0), (3,4): (0,0,1),
     (4,0): (1,0,0), (4,1): (1,0,0), (4,2): (1,0,0), (4,3): (0,1,0)}
pairs = 0
for (i,j) in itertools.permutations(range(5), 2):
    c1=M[(i,j)][0]
    c2=M[(i,j)][1]
    c3=M[(i,j)][2]
    (v1,v2,v3)=[v for v in range(5) if (v!=i and v!=j)]
    for a in range(1 << 5):
        assert((a>>v1)&1!=c1 or
               (a>>v2)&1!=c2 or
               (a>>v3)&1!=c3 or
               tt[a]==(a>>i)&1
               )
    pairs += 1
print('script (i): witness table M verified for', pairs, 'ordered pairs (positive sign only)')

# ---- script (ii), verbatim ----
tt=[0,0,0,0,0,0,1,1,0,1,0,1,1,1,1,0,0,1,1,1,0,1,1,0,0,1,1,0,1,0,0,0]
rows = 0
for (x0,x1,x2,x3,x4) in itertools.product(range(2), repeat=5):
    g1=(x1+x2)%2 # x1 xor x2
    g2=(x2+x3)%2 # x2 xor x3
    g3=(x0+x2)%2 # x0 xor x2
    g4=(x1+x4)%2 # x1 xor x4
    g5=1-(1-g2)*(1-g4) # g2 or g4
    g6=1-(1-x3)*(1-x4) # x3 or x4
    g7=x3*g4 # x3 and g4
    g8=g1*(1-g7) # g1 and (not g7)
    g9=(1-g3)*g6 # (not g3) and g6
    g10=g5*(1-g9) # g5 and (not g9)
    g11=(g8+g10)%2 # g8 xor g10
    assert(g11==tt[x0+2*x1+4*x2+8*x3+16*x4])
    rows += 1
print('script (ii): 11-gate circuit matches the printed truth table on', rows, 'rows')
print('integer truth table (bit a = tt[a]):', sum(b << a for a, b in enumerate(tt)))

# ---- WP1 JSON form of the Appendix circuit (nodes 0..4 = x0..x4, 5..15 = g1..g11; truth table f00 f01 f10 f11) ----
XOR, OR, AND, ANDN = (0,1,1,0), (0,1,1,1), (0,0,0,1), (0,0,1,0)   # ANDN(a,b) = a and not b
NAND_ = (0,1,0,0)                                                 # (not a) and b
APPENDIX_CIRCUIT = dict(n=5, gates=[
    (1, 2, XOR),      # g1 = x1 xor x2      node 5
    (2, 3, XOR),      # g2 = x2 xor x3      node 6
    (0, 2, XOR),      # g3 = x0 xor x2      node 7
    (1, 4, XOR),      # g4 = x1 xor x4      node 8
    (6, 8, OR),       # g5 = g2 or g4       node 9
    (3, 4, OR),       # g6 = x3 or x4       node 10
    (3, 8, AND),      # g7 = x3 and g4      node 11
    (5, 11, ANDN),    # g8 = g1 and not g7  node 12
    (7, 10, NAND_),   # g9 = not g3 and g6  node 13
    (9, 13, ANDN),    # g10 = g5 and not g9 node 14
    (12, 14, XOR),    # g11 = g8 xor g10    node 15
], outputs=[15])
if __name__ == '__main__':
    json.dump(APPENDIX_CIRCUIT, open('appendix_circuit.json', 'w'))
    print('circuit JSON written to appendix_circuit.json')
    sys.exit(0)
