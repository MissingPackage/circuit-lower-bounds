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
| WP2c | Gadget question closed for all k: 1-stable with <= 6 gates needs k <= 7 (hand argument A), (k, k-1) excluded (hand argument B), remaining SAT instances at k = 6, 7 | done with open instances: 0 SAT rows; (6,5) UNSAT in mode full (1341 s); (6,6) and (7,6) TIMEOUT in mode full; mode-none cross-checks time out from s = 4; global claim not made by the pre-registered rule, A and B stand as hand proofs |
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

## WP2c summary (the gadget question for every k)

Question: does any 1-stable function (GHKK Definition 2, both signs) on k >= 6
inputs have <= 6 gates, i.e. can the WP2b gadget (7 gates, k = 5) be beaten at
all?  Pre-registration: `wp2c_preregistration_2026-10-11.txt`
(`wp2c_frozen.stamp`).  Nothing here is a lower bound.

Hand arguments (written in the pre-registration before the runs, hand-checked
only, no machine proof):

- **A** (k <= s + 1): a 1-stable function depends on every input (Definition 2
  with |Y| = 1 leaves a non-constant function of y), and a function that depends
  on k inputs needs >= k - 1 gates (the output cone is a connected DAG with
  k + g' nodes and 2 g' edges, so g' >= k - 1).  Hence a 1-stable gadget with
  s gates has k <= s + 1; with WP2 (no 1-stable function for k <= 4) and WP2b
  (minimum 7 at k = 5) the only candidates for "<= 6 gates" are
  (k, s) in {(6, 5), (6, 6), (7, 6)}.
- **B** (tree lemma, (k, k - 1) impossible): if the circuit has exactly k - 1
  gates, the cone is a tree (every node has fan-out 1).  Take any input x, its
  unique gate G = op(u, x) and an input y below u; for Y = {y, x} and the element
  y, under any restriction tau of the other inputs u becomes 0, 1, y or not y:
  constant kills y, a literal makes G depend on x (op non-degenerate) and the
  rest of the tree is a function of G alone.  So Definition 2 fails and the
  function is not 1-stable.  This disposes of (6, 5) and (7, 6) by hand; the only
  instance not fixed by A and B is (6, 6) (a tree plus one extra edge).

SAT runs (`results_wp2c.csv`, `log_wp2c.txt`, `results_wp2c_min.csv`; runner
`run_wp2.py`, 1 worker, hard 3600 s per instance, variant stable1, essential
flag 0, modes `full` = WP1 symmetry breaking and `none` = plain encoding):

| (k, s)   | mode full                  | mode none                  | declaration (brief rule) |
|----------|----------------------------|----------------------------|--------------------------|
| (6, 0-3) | UNSAT, <= 1.6 s            | UNSAT, <= 24.0 s           | sanity (UNSAT by A)      |
| (6, 4)   | UNSAT, 44.3 s              | TIMEOUT 3600 s             | sanity (UNSAT by A)      |
| (7, 0-3) | UNSAT, <= 9.0 s            | UNSAT, <= 54.8 s           | sanity (UNSAT by A)      |
| (7, 4)   | UNSAT, 235.6 s             | not run (budget)           | sanity (UNSAT by A)      |
| (7, 5)   | TIMEOUT 3600 s             | not run (budget)           | sanity (UNSAT by A)      |
| (6, 5)   | UNSAT, 1340.6 s            | not run (budget)           | open (brief rule); UNSAT by B |
| (7, 6)   | TIMEOUT 3600 s             | not run (budget)           | open (brief rule); UNSAT by B |
| (6, 6)   | TIMEOUT 3600 s             | not run (budget)           | open                     |

No SAT row appeared anywhere (P1 holds; P5 not exercised).  Controls before the
runs (`wp2c_controls.py`, `log_wp2c_controls.txt`, `results_wp2c_smoke.csv`,
50 checks, 0 failures): the checker at k = 6, 7 rejects x1x2x3 xor x4x5x6
(weak1 accept), rejects gst1, the WP2b argmin and the WP2 function padded with
dummy inputs (exactly the six (Y, y) tests involving the dummy input fail),
accepts a random 6-input function (104 of 2000 random 64-bit tables are
1-stable); the encoder builds 64- and 128-row free and fixed instances; the
k = 6 weak1 search gives SAT at s = 3 in both modes with sim pass and checker
accept, and AND_6 / AND_7 give the known values 5 / 6.

Operational deviations (recorded in `log_wp2c.txt`): the pre-registered run
order put all sanity rows first; after the (6, 4) mode-none row used its full
3600 s the runner was stopped and relaunched twice so that the open instances,
in particular (6, 6) mode full, ran before the k = 7 mode-none sanity rows.
Instance timeouts and the 1-worker setting were not changed.  The summary file
`results_wp2c_min.csv` lacks the (6, 4) none row (runner stopped right after
the instance row); `results_wp2c.csv` is authoritative.

### What is now established about the GHKK ceiling

- For the measure mu_alpha(C) = gates(C) + alpha * inputs(C) and 1-substitutions,
  GHKK Theorem 4 gives, for h = f <> g with g 1-stable,
  mu_alpha(h) - mu_alpha(h|rho) <= gates(g) + alpha for every 1-substitution
  rho, and Corollary 6 instantiates it with gst1 (11 gates): the method cannot
  prove better than 11n with these tools.  With the WP2b gadget (7 gates, class
  0x00071357) the same corollary gives 7 + alpha per substitution, i.e. a
  ceiling of about 7n for plain gate elimination with mu_alpha and
  1-substitutions.  This is a limit on the method, not a lower bound on any
  function; the composition argument is GHKK's and is not re-proved here.
- Whether 7 can be lowered further.  For k <= 5 the answer is machine-checked:
  no 1-stable function for k <= 4 (WP2, exhaustive) and minimum 7 at k = 5
  (WP2b, Knuth's table, SAT-confirmed).  For k >= 6, Argument A limits a
  cheaper gadget to k in {6, 7} and Argument B excludes (6, 5) and (7, 6), so
  the whole question reduces to one instance: is some 6-input function computed
  by a 6-gate circuit (a tree plus one extra edge) 1-stable?  The SAT runs agree
  with A on all 19 completed rows (0 SAT) and with B on (6, 5) in mode full
  (UNSAT, 1341 s); (6, 6) timed out in mode full and the mode-none
  cross-checks of the open instances did not complete.  By the pre-registered
  rule (UNSAT in both modes) no open instance is declared and the claim "7 is
  the minimum gadget size for this framework" is NOT made.  What stands is:
  7 is the minimum for k <= 5 (machine-checked); for every k the only
  remaining candidate below 7 is (k, s) = (6, 6), open, with A and B as
  hand proofs that have not been machine-checked beyond the rows above.
- Remaining open: m >= 2 substitutions (2-stable gadgets: none exist for
  k <= 5 by WP2/WP2b; k >= 6 not searched here), non-subadditive potentials
  (the Li-Yang 3.1n proof uses a measure outside Theorem 4's hypotheses), and
  gadgets for measures other than mu_alpha.
- Not verified: UNSAT answers are not DRAT-certified; the symmetry-breaking
  mode `full` has no independent counter-check at k >= 5 except the mode-none
  runs listed above, which time out from s = 4 at k = 6 and were not run for
  k = 7, s >= 4; Arguments A and B are
  hand proofs with no machine check beyond the SAT rows they predict.

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
- `wp2c_controls.py`, `wp2c_verify_sat.py`, `analyze_wp2c.py` — WP2c: controls at
  k = 6, 7, verification ladder for SAT rows (exercised on the smoke rows,
  `log_wp2c_verify_smoke.txt`), metric reader; `results_wp2c*.csv`,
  `log_wp2c*.txt` — WP2c outputs
- `sources/` — transcribed reference values with citations; third-party
  documents are not redistributed (see `sources/SOURCES.md`)

## Setup

```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run_all.py --help
```
