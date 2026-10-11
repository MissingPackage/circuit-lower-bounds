"""Decoder check against the only published program output of optimal5: README.md lists the chain that
human_readable.cpp prints for the truth table 0x169ae443 (the unique cost-12 class).  The decoded record for
that class must print the same 12 operations in the same order with the same operand order.
Exit status 0 iff identical."""
import sys
import optimal5_glue as g

README_CHAIN = ('x6 = x4 & x2; x7 = x4 | x2; x8 = x5 &~ x7; x9 = x7 &~ x5; x10 = x1 ^ x8; x11 = x10 & x3; '
                'x12 = x11 | x9; x13 = x6 & x1; x14 = x12 &~ x13; x15 = x4 &~ x3; x16 = x14 ^ x15; x17 = x16 ^ x1; result = x17')


def main():
    recs = g.load_records()
    index = {g.chain_tt_opt5(r): i for i, r in enumerate(recs)}
    w = 0x169ae443
    orb = g.orbit_opt5(g.opt5_to_wp1(w))
    hits = [x for x in orb if x in index]
    print('0x169ae443: orbit size', len(orb), 'representatives in orbit', ['%08x' % h for h in hits])
    got = g.chain_text(recs[index[w]])
    print('decoded:', got)
    print('README :', README_CHAIN)
    ok = hits == [w] and got == README_CHAIN and len(recs[index[w]]) == 12
    print('identical:', ok)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
