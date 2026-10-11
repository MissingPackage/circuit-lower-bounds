# circuit-lower-bounds

Machine-assisted search around circuit lower bounds for explicit Boolean
functions over the full binary basis B2, organised as prediction-gated work
packages (pre-register -> execute -> independent grading).

The motivating question is the gate-elimination ladder 3n -> 3.011n -> 3.1n
(Li-Yang 2022) and whether machine-scale case analysis can move it. Every
work package states up front what would refute it; results are only claimed
with the raw artifacts (frozen targets, CSV results, logs) committed.

## Work packages

| WP  | Object searched | Status |
|-----|-----------------|--------|
| WP1 | SAT encoder for exact circuit size of small functions, validated against known values | done, confirmed by independent grader |
| WP2 | Cheaper m-stable gadgets (tighter ceiling for plain gate elimination, GHKK 2016) | in progress (k=5 SAT ladders running) |
| WP2b | WP2 k=5 question answered by lookup in Knuth's table of optimal 5-input chains (via optimal5) | done: min over 1-stable classes = 7 (gst1 has 11); confirmed by SAT, simulation and checker |
| WP3 | Automated search for gate-elimination potentials and case analyses | planned |

## WP1 summary

Encoder: predecessor-selection variables + 4-bit truth table per gate, one
value per gate per input row, output constrained to f (after
Kojevnikov-Kulikov-Yaroslavtsev 2009). Solver: cadical195 via python-sat.
Optional symmetry breaking (normal gates, no degenerate gates, every gate
used, colex ordering, first-use ordering of inputs for symmetric functions).
Because the "every gate used" constraint makes the encoding non-monotone in
s, an exact value is only declared with UNSAT for *every* s' < s.

Results: 27/27 frozen targets reproduced (UNSAT below, SAT at, simulation
pass); 256/256 three-variable functions agree with an independent BFS
enumeration, with and without symmetry breaking; 0 extracted circuits fail
simulation; 0 timeouts (max 4.9 s for n<=4, 1452 s for n=5 on 2 cores).

Known limits: UNSAT answers are not independently certified (no DRAT
check); symmetry breaking at n=5 has no independent counter-check; three
target values (MAJ_5, THR2_4, THR3_4) rest only on an operator-glyph count
extracted from a figure of Knuth's draft 7.1.2 (independently confirmed by the
WP2b table lookup: 9, 7, 7).

## WP2b summary (table lookup for k = 5)

Question: minimum circuit size C(f) over all 1-stable 5-input functions (GHKK
Definition 2, both signs), over weakly 1-stable (Definition 1) and over 2-stable
functions. Pre-registration: `wp2b_preregistration_2026-10-11.txt`
(`wp2b_frozen.stamp`). Nothing here is a lower bound.

Method. Knuth's optimal chains for all 616,126 NPN classes of 5-input functions
(TAOCP 7.1.2, program BOOLCHAINS) as packaged by apgoucher/optimal5
(`knuthies.dat`, read from a read-only clone, see `sources/SOURCES.md`). No C++
compiler exists on the host, so the data file is decoded in pure Python
(`optimal5_glue.py`, mirror of `bytes2gv()` in `optimal5.h`). Steps and results:

1. NPN invariance (`npn_invariance.py`, `log_wp2b_invariance.txt`): m-stability
   (both signs) and weak m-stability are invariant under input permutation, input
   negation and output negation (argument in the script docstring); mechanically,
   0 verdict changes of `stable_check.py` over 2400 (f, random NPN transform)
   pairs per variant (302 stable1 positives, 2247 weak1 positives; stable2 has no
   positives at k=5, so its invariance rests on the argument). The positive-sign
   variant `stable1pos` is not invariant (22 changes; NOT gst1 is rejected by it
   and accepted by stable1). Hence the 616,126 class representatives suffice; the
   2^32 enumeration was not needed and was not run.
2. Table validation before use (`wp2b_run.py`, `log_wp2b.txt`,
   `results_wp2b_knuth_hist.csv`): 616,124 records decode without garbage, keys
   are distinct, every key is the minimum of its NPN orbit (checked for all 3840
   input transformations of every key), class histogram per cost = Knuth's 2, 2,
   5, 20, 93, 389, 1988, 11382, 60713, 221541, 293455, 26535, 1 and function
   histogram (orbit sizes) = 12, 100, 1140, 11570, 109826, 995240, 8430800,
   63401728, 383877392, 1519125536, 2123645248, 195366784, 1920, summing to 2^32
   (all 26 cells equal to `checktab.py`). The decoded chain of 0x169ae443 is
   identical to the one printed in the optimal5 README (`wp2b_readme_check.py`).
3. Cost-convention cross-check (`results_wp2b_crosscheck.csv`, 312 rows): all
   single-output WP1 targets with n <= 5, gst1, the WP2 SAT-found function, all 256
   three-input functions of `results_bfs3.csv` and the 32 symmetric four-input
   functions of `results_sym4_min.csv` (smaller n padded with dummy inputs).
   Equality everywhere except (a) exactly the 7 predicted degenerate rows (constants
   and negated literals: 1 gate in WP1, which needs a gate node, 0 in Knuth, where
   constants, literals and negation are free) and (b) the WP2 function tt=9178798,
   whose WP2 value 11 was an upper bound (SAT at s=11 only): the table says 7, and
   our own encoder confirms it (below). Every decoded and NPN-transformed circuit
   with >= 1 gate re-simulates to the target (302/302 pass). The three WP1 rows
   that rested only on a glyph count (MAJ_5 = 9, THR2_4 = 7, THR3_4 = 7) are
   confirmed by the table. Convention mismatches found: truth-table bit order
   (optimal5 bit b is f at x_j = 1 - ((b >> (5-j)) & 1); WP1 bit t is f at
   x_{i+1} = (t >> i) & 1; converted explicitly), zero-cost constants/literals/
   negations (above), and gate basis {AND, OR, XOR, AND-NOT} on normalised chains
   versus all 16 gate types in WP1 (no cost difference: negations are absorbed into
   gate types in both).
4. Results (`results_wp2b_classes.csv` one row per class,
   `results_wp2b_stability_hist.csv`, `results_wp2b_argmin.csv`):
   - 1-stable: 584 classes, 3,526,656 functions; cost histogram (classes) 7:1,
     8:10, 9:119, 10:342, 11:111, 12:1. **Minimum 7**, attained by exactly one
     class, representative 0x00071357 (WP1 TT_5_3939033088, orbit 768, all inputs
     essential, also 1-stable in the positive-sign-only sense), chain
     `x6 = x2 & x3; x7 = x6 | x1; x8 = x5 & x2; x9 = x8 | x4; x10 = x7 & x9;
     x11 = x5 | x3; x12 = x10 & x11` (monotone). The WP2 SAT-found function
     tt=9178798 belongs to this class; gst1 (class 0x035e7668) has cost 11 and is
     not an argmin. Verification beyond the table (`log_wp2b_sat.txt`): the decoded
     circuit passes `simulate.py` and the independent bit-parallel simulation,
     `stable_check.py --variant stable1` accepts the function, and the WP1 encoder
     gives UNSAT at s = 0..6 and SAT at s = 7 (sim pass) for both TT_5_3939033088
     and TT_5_9178798 (max 9 s per instance). So the GHKK Corollary 6 ceiling for
     1-substitutions with the measure mu_alpha tightens from 11 + alpha to
     7 + alpha with this gadget (a ceiling statement about the method, not a lower
     bound; the composition argument of Corollary 6 is GHKK's and is not re-proved
     here).
   - weakly 1-stable: 561,436 classes (3,955,120,408 functions); minimum 3 with
     dummy inputs allowed (3 classes, e.g. x2x3 xor x1x4), minimum 4 with all five
     inputs essential (6 classes), as predicted.
   - 2-stable: 0 classes at k = 5, as predicted.
   Pre-registered P1 and P2 hold in full; P3 is refuted on its main claim
   (predicted minimum 11, found 7) and holds on weak1 (3 / 4) and stable2 (0).

Limits. Knuth's chains are used as published (validated by histogram, orbit
sum, README example and 312 cross-checks, not re-derived); the exactness of 7
from our side rests on WP1-encoder UNSAT answers in mode `full`, which are not
DRAT-certified (same caveat as WP1); the stable2 invariance test had no
positive instances at k = 5. The running WP2 SAT ladders (`results_wp2_k5.csv`)
were not touched.

## Layout

- `encoder.py`, `solve.py`, `simulate.py`, `funcs.py` — encoder, per-instance
  solver wrapper (child process with hard timeout), truth-table simulator,
  target functions
- `bfs3.py` — independent exhaustive enumeration for n=3 (shares no code with
  the encoder)
- `run_all.py`, `analyze.py` — campaign runner and metric recount
- `targets_frozen_*.csv`, `targets_frozen.stamp` — pre-registered expected
  values with sha256 stamp taken before the first run
- `results_*.csv`, `log_*.txt` — raw outputs
- `optimal5_glue.py`, `wp2b_run.py`, `npn_invariance.py`, `wp2b_readme_check.py`
  — WP2b: decoder for Knuth's table (optimal5), driver, NPN-invariance test,
  decoder check against the optimal5 README; `results_wp2b_*.csv`,
  `log_wp2b*.txt` — WP2b outputs (`results_wp2b_classes.csv` has one row per
  NPN class, 616,126 rows)
- `sources/` — transcribed reference values with citations; third-party
  documents are not redistributed (see `sources/SOURCES.md`)

## Setup

```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run_all.py --help
```
