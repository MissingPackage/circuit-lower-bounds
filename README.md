# circuit-lower-bounds

Machine-assisted search around circuit lower bounds for explicit Boolean
functions over the full binary basis B2, organised as prediction-gated work
packages (pre-register -> execute -> independent grading).

The motivating question is the gate-elimination ladder 3n -> 3.011n -> 3.1n
(Li-Yang 2022) and whether machine-scale case analysis can move it. Every
work package states up front what would refute it; results are only claimed
with the raw artifacts (frozen targets, CSV results, logs) committed.

## What is established (gadget question, status after WP2d)

For the plain gate-elimination method with the measure mu_alpha = gates + alpha
* inputs and 1-substitutions (GHKK Theorem 4 / Corollary 6), the smallest
1-stable gadget (Definition 2, both signs) has exactly 7 gates: no 1-stable
function on any number of inputs has a B2 circuit with <= 6 gates, and the
7-gate class 0x00071357 on 5 inputs exists.  Hence no 1-stable gadget can
push the Theorem 4 bound below 7 + alpha per substitution: 7n is the best
ceiling obtainable from Theorem 4 / Corollary 6 with a 1-stable gadget (it
does not show that the method cannot be limited further by other means).
Scope: this is the mu_alpha / 1-substitution ceiling of GHKK Corollary 6 (11n
in their paper).  For the plain gate-count measure GHKK Section 3.2 already
gives a 5n ceiling via f composed with MAJ_3, and 5n is the figure quoted by
later work (Golovnev-Kulikov-Williams, ITCS 2021); that bound is unaffected
here.  Evidence chain: k <= 4 none
(WP2, exhaustive over all truth tables); k = 5 minimum 7 (WP2b, Knuth's table,
SAT-confirmed); k >= 6: a 1-stable function depends on every input, so s gates
force k <= s + 1 (Argument A, hand proof), which leaves (k, s) in {(6, 5),
(6, 6), (7, 6)}; all three are closed by exhaustive enumeration of every circuit
DAG with every node in the output cone and normalised gate types (WP2d, reductions
R1-R3 proved in `wp2d_preregistration_2026-10-12.txt`, enumerator validated
against Knuth's cost histogram at k = 5 and against bfs3 at k = 3): 0 of
29,005 + 1,399,372 + 437,025 produced functions are 1-stable, (6, 5) also UNSAT
by SAT (WP2c).  This is a limit on what that proof method can give, NOT a lower
bound on any function; it says nothing about m >= 2 substitutions,
non-subadditive potentials or other measures.  Caveats: the global claim is
made on the strength of the enumeration (a documented deviation from the WP2c
rule that demanded UNSAT in both SAT modes); the k = 5 value rests on Knuth's
table as published plus non-DRAT-certified UNSAT answers.

## What is established (gates-only measure, status after WP2e)

For the plain gate-count measure, B2 circuits and one substitution per step
(the substituted variable replaced by an arbitrary function of the others),
GHKK's own Theorem 1 (subadditive measure, weakly m-stable gadget; the paper
names gates as subadditive, PDF p.8) gives the ceiling gates(g) per
substitution for every weakly 1-stable gadget g.  The 5 of GHKK Section 3.2
(PDF p.7) is the authors' "the majority of three bits can be computed in five
gates", an upper bound on gates(MAJ_3) that is not tight (gates(MAJ_3) = 4).
With MUX_3 (x1 ? x2 : x3, 3 gates, SAT-proven and exhaustive) the ceiling
becomes 3 per substitution, i.e. 3n instead of the 5n quoted by later work,
and 3 is the minimum over all weakly 1-stable gadgets on any number of inputs
(exhaustive enumeration: none with <= 2 gates).  The Section 3.2 proof
re-derived for MUX_3 is in the WP2e summary below.  This limits a proof
method; it is NOT a circuit lower bound for any function.  It refines the
sentence "that bound is unaffected here" in the section above, which was
written for WP2d and is kept as it was.

Scope of the 3n statement (do not quote it without these qualifiers): it
covers gate-elimination arguments in the GHKK framework (PDF p.5-6) with the
pure gates measure, one substitution per step, and an induction step that
must hold for every function (the class contains h = f <> MUX_3 for arbitrary
f).  It does not cover measures with an input term such as gates + alpha *
inputs (Find-Golovnev-Hirsch-Kulikov 2016, Li-Yang 2022; there Theorem 4 with
a 1-stable gadget applies, 7n after WP2d), nor m >= 2 substitutions per step
(Stockmeyer), nor function-specific steps.  Consistency check: Blum's 3n -
o(n) (1984) uses the gates measure and gains 3 gates per substitution, exactly
the ceiling, and GHKK (PDF p.4, p.6) place his argument outside the framework
because its second case counts gates of out-degree >= 2 using a property of
the specific function rather than a substitution gain.  The ceiling and Blum
therefore agree on 3 for gates-only arguments of this type.  Reviewed
adversarially (independent re-implementation of the repair check, 19,200
random cases, 0 failures; independent brute force over all circuits with <=
2 gates on <= 4 inputs, 0 weakly 1-stable functions).

## Work packages

| WP  | Object searched | Status |
|-----|-----------------|--------|
| WP1 | SAT encoder for exact circuit size of small functions, validated against known values | done, confirmed by independent grader |
| WP2 | Cheaper m-stable gadgets (tighter ceiling for plain gate elimination, GHKK 2016) | done: no 1-stable function on 3 or 4 inputs (exhaustive + SAT); at k=5 the SAT search found an 11-gate 1-stable function in 9.5 s but the free-function ladder stopped at s=5 (s=6 timed out); the k=5 question was then answered by WP2b |
| WP2b | WP2 k=5 question answered by lookup in Knuth's table of optimal 5-input chains (via optimal5) | done: min over 1-stable classes = 7 (gst1 has 11); confirmed by SAT, simulation and checker |
| WP2c | Gadget question closed for all k: 1-stable with <= 6 gates needs k <= 7 (hand argument A), (k, k-1) excluded (hand argument B), remaining SAT instances at k = 6, 7 | done with open instances: 0 SAT rows; (6,5) UNSAT in mode full (1341 s); (6,6) and (7,6) TIMEOUT in mode full; mode-none cross-checks time out from s = 4; global claim not made by the pre-registered rule, A and B stand as hand proofs |
| WP2d | Mechanical closure of the gadget question for every k: exhaustive enumeration of circuit DAG structures at (6,5), (6,6), (7,6) plus regression instances, re-derived independently of the WP2c reviewer's scripts | done: 0 1-stable functions among 29,005 / 1,399,372 / 437,025 distinct functions (and 0 at (4,4), (5,5), (5,6)); enumerator completeness validated against Knuth's cumulative class histogram at k = 5 (s = 0..7, every class hit, 0 containment violations, the 7-gate argmin found at s = 7) and against bfs3 at k = 3; global claim "7 is the minimum gadget size" declared on the enumeration (documented deviation from the WP2c both-SAT-modes rule) |
| WP2e | Gates-only ceiling of plain gate elimination (GHKK Section 3.2 "5n"): what Theorem 1 gives with the cheapest weakly 1-stable gadget | done: Section 3.2's 5 is a non-tight MAJ_3 size bound; Theorem 1 with mu = gates gives gates(g); minimum over weakly 1-stable g is 3 (MUX_3; 0 weakly 1-stable tables with <= 2 gates, exhaustive), so the ceiling is 3n; a limit on a proof method, not a lower bound |
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

## WP2 summary (SAT search for cheaper m-stable gadgets)

Question: GHKK (Golovnev, Hirsch, Knop, Kulikov, "On the Limits of Gate
Elimination") report a 1-stable function on 5 inputs computable with 11 gates
(Lemma 4) and derive Corollary 6: plain gate elimination with the measure
mu_alpha = gates + alpha*inputs and single substitutions cannot prove 11n. Is
there a 1-stable function (Definition 2) with fewer gates? Pre-registration:
`wp2_preregistration_2026-10-11.txt` (`wp2_frozen.stamp`); definitions
transcribed verbatim in `sources/GHKK_TRANSCRIPTION_2026-10-11.txt`. Nothing
here is a lower bound.

Code added: a free-function path in `encoder.py` (regression: 216/216 fixed
target instances produce identical CNF), `stability.py` (SAT-side encoding of
Definitions 1 and 2 plus an essential-inputs flag), `stable_check.py` (an
independent bit-parallel brute-force checker sharing no code with the SAT side,
cross-validated 3557/3557 against a naive re-implementation), `appendix_a.py`
(verbatim port of the two GHKK Appendix A scripts; both pass, and the Appendix
11-gate circuit passes `simulate.py` and the checker).

Results (`results_wp2_k34.csv`, `log_wp2_counts.txt`, `results_wp2_k5.csv`,
`log_wp2_k5.txt`):

- k = 3, 4: no 1-stable function exists (exhaustive over all 256 and 65,536
  truth tables; SAT UNSAT at s <= 4 and s <= 7 in both modes). No 2-stable
  function on <= 4 inputs. Weakly 1-stable minimum 3 at k = 3 (MUX_3) and 3 at
  k = 4 with every input essential.
- k = 5: the joint search (free function + 1-stability) is SAT at s = 11 in
  9.5 s (truth table 9178798; WP2b later showed its exact cost is 7). The
  free-function ladder is UNSAT at s <= 5 (312 s at s = 5) and timed out at
  s = 6 (6280 s). The fixed ladder on GHKK's gst1 is UNSAT at s <= 7 (75 s at
  s = 7), timed out at s = 8 (7200 s) and at s = 11 (3600 s); s = 9, 10 were
  skipped at the run deadline. 2-stable: UNSAT at every s run (<= 10).
  Positive-sign 1-stable (the Appendix A notion): SAT at s = 11 in 29 s.
- 0 SAT rows fail simulation or the checker; 0 timeouts recorded as UNSAT.

Grader verdict at grading time: inconclusive (k = 5 still running). The k = 5
question was then answered by table lookup in WP2b. Not verified: UNSAT rows
carry no DRAT certificate; symmetry breaking at k = 5 has no independent
counter-check (the mode-none free search did not finish).

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

## WP2d summary (mechanical closure by exhaustive enumeration)

Question: the WP2c instances (6, 5), (6, 6), (7, 6) left by Argument A, closed
here by exhaustive enumeration of circuit DAG structures instead of SAT, with
the enumeration re-derived from scratch (the adversarial reviewer's scripts in
`wp2d/reviewer_scripts/` were read only after my enumerator had produced its
first full counts).  Pre-registration: `wp2d_preregistration_2026-10-12.txt`
(`wp2d_frozen.stamp`).  Nothing here is a lower bound.

Reductions (statements and proofs in the pre-registration): R1 every circuit of
non-degenerate gates has a same-structure circuit over the 5 normal types
{AND, OR, XOR, a AND NOT b, NOT a AND b} computing f or NOT f (output negations
absorbed downstream; constants and projections handled at s = 0 by hand); R2 a
degenerate gate (degenerate type, or both arguments the same node) can be
bypassed, so a minimum circuit has only non-degenerate gates with distinct
arguments, every gate and every essential input in the output cone; R3
1-stability and weak 1-stability are invariant under input permutation, input
negation and output negation (tested mechanically at k = 6, 7:
`wp2d_npn_invariance.py`, `log_wp2d_invariance.txt`, 2000 (f, random NPN
transform) pairs per k, 0 verdict changes for stable1 (430 / 1322 positives)
and weak1, stable1pos not invariant: 4 / 57 changes; every stable1 positive is
weak1 and depends on every input).  Hence it suffices to enumerate, per (k, s),
every DAG with k inputs and s gates in which every node lies in the output cone,
inputs labelled by first use, gate types from the 5 normal types, and to test
the positive sign only.

Enumerator (`wp2d_enum.py`): depth-first structure search with the counting
bound "nodes without a reader <= remaining gates + 1" and a canonical
topological order (adjacent independent gates in non-decreasing order; sound by
a lexicographic-minimum argument), then all 5^s type assignments, with two
evaluators over the same structure generator (pure-Python bit-parallel DFS and a
numpy per-structure vectorisation); self-test `log_wp2d_selftest.txt` (structure
counts against the stand-alone counter `wp2d_struct_count.py`, dfs == vec on 10
instances, witnesses re-simulate with `simulate.py` and `stable_check.py`).
Verdicts: `stable_check` test lists applied to every distinct truth table, plus
a numpy vectorisation of the same lists as a cross-check (validated on 38,400
sampled tables, 0 mismatches).

Completeness controls (`log_wp2d_control3.txt`, `results_wp2d_bfs3.csv`,
`log_wp2d_control5.txt`, `results_wp2d_control5.csv`):

- k = 3: the enumerator cost (min s with f or NOT f produced, constants and
  projections at s = 0) equals `bfs_min` of `results_bfs3.csv` on 251 of 256
  rows; the 5 exceptions are exactly tt 0, 255, 85, 51, 15 (constants and
  negated literals: 1 gate in bfs3, 0 here), as pre-registered.
- k = 5 (unused inputs allowed, i.e. the padded union over j <= 5 inputs with
  all j used): the NPN classes of `results_wp2b_classes.csv` hit by E(<= s) are
  exactly 2, 4, 9, 29, 122, 511, 2499 for s = 0..6 (the cumulative Knuth
  histogram), also per number of essential inputs (5 essential: 0, 0, 0, 0, 59,
  373, 2289; 4 essential: 0, 0, 0, 17, 49, 124, 196; 3: 0, 0, 5, 8, 10, 10, 10),
  with 0 containment violations (every produced table lies in the orbit of a
  class of cost <= s) and 0 stable1 tables among the 870,677 produced for
  s <= 6.  At s = 7 (run after a container restart, `log_wp2d_control5.txt`, 1702 s): 13,881 classes hit of 13,881 (5 essential: 13,659; 4: 208), 0 containment violations over 9,219,713 produced tables, and 192 stable1 tables, all canonicalising to the single class 0x00071357 (the WP2b argmin): the enumerator reaches the first gadget exactly at the size where it exists.
- Every 4-input function appears by s = 7 (all 65,536 after expansion over
  permutations and negation: cover 65,536/65,536 at s = 7, j = 4); all 256 three-input functions by
  s = 4 (s = 5, 6 add nothing).

Main runs (`results_wp2d_main.csv`, `log_wp2d_main.txt`, sets in
`wp2d/E_k_s.npy`; status: exhaustive):

| (k, s) | structures | leaves (structures x 5^s) | distinct functions | depend on all k inputs | stable1 |
|--------|-----------:|--------------------------:|-------------------:|-----------------------:|--------:|
| (4, 4) | 35  | 21,875     | 2,365     | 2,200     | 0 |
| (5, 5) | 148 | 462,500    | 58,009    | 55,932    | 0 |
| (5, 6) | 3,403 | 53,171,875 | 845,540 | 826,609   | 0 |
| (6, 5) | 15  | 46,875     | 29,005    | 29,005    | 0 |
| (6, 6) | 672 | 10,500,000 | 1,399,372 | 1,366,464 | 0 |
| (7, 6) | 52  | 812,500    | 437,025   | 437,025   | 0 |

Both evaluators give byte-identical sets on all six instances; the stable1
count is 0 by the per-table checker and by the vectorised predicate (k <= 6).
(6, 5) and (7, 6) are forced to be trees and every produced function depends
on all inputs, consistent with the tree lemma; (6, 6) is a tree plus one edge.

Comparison with the reviewer's enumeration (`wp2d_compare.py`,
`results_wp2d_compare.csv`, `log_wp2d_compare.txt`; the reviewer's scripts rerun
verbatim, their sets in `wp2d/R_k_s.npy`): (6, 5) 29,005 and (7, 6) 437,025
reproduced to the integer with identical sets; the reviewer's `topo.py` has no
canonical topological-order rule, so on non-tree instances it visits several
first-use labellings of the same DAG and its sets are strict supersets of mine
by permutation images only: (4, 4) 2,901 vs 2,365 and (5, 5) 73,089 vs 58,009
with identical canonical forms under input permutation (417 and 6,228 classes);
(6, 6): 1,857,928 vs 1,399,372, again a strict superset by permutation images only, with identical canonical forms (86,316 classes on both sides, `results_wp2d_compare.csv`, `canon_equal = 1`).  The reviewer's "0 stable1" counts are thereby reproduced
and the status of their numbers moves from reported-unreviewed to reproduced.

Outcome: P1-P3 hold (P3's integer prediction for (6, 6) only after the
convention alignment foreseen in the pre-registration).  The global claim "7
is the minimum gadget size for this framework" is declared on the strength of
the enumeration; this is a documented deviation from the WP2c rule (UNSAT in
both SAT modes), and the WP2c section above keeps its statement that (6, 6)
was open at that time.  The Corollary 6 ceiling with mu_alpha and
1-substitutions obtainable from a 1-stable gadget is 7n and cannot be lowered
by a better gadget: a limit on the method, not a lower bound.
Not verified: the k = 5 minimum is Knuth's table plus non-DRAT UNSAT answers
(WP2b); the enumeration itself is validated by the controls above, not
independently re-derived a third time.  Dependency added: numpy (vectorised
evaluator and controls); the main runs also have the pure-Python evaluator.

## WP2e summary (the gates-only ceiling: 5n -> 3n)

Question: GHKK Section 3.2 shows, for h = f <> MAJ_3, that no 1-substitution
removes more than 5 gates, and later work quotes this as "gate elimination
cannot prove better than 5n".  Their Theorem 1 (subadditive mu, weakly
m-stable g) would give gates(g) with a weakly 1-stable g; WP2 found MUX_3
(3 gates).  Which constant is right, and what is the smallest gadget?
Stage 1 reading: `wp2e_stage1_reading_2026-10-12.txt` (PDF re-fetched,
sha256 identical to WP2).  Pre-registration: `wp2e_preregistration_2026-10-12.txt`
(`wp2e_frozen.stamp`, stamped before any stage 2 code).  Nothing here is a
lower bound: it limits a proof method.

Stage 1 (reading, page-quoted; status READ unless marked):

- Section 3.2 (PDF p.7): measure gates; substitution "x_ij <- rho, where rho
  is any function of all the remaining variables", which is a Section 3.1
  1-substitution (PDF p.6); circuit model of Section 1 (PDF p.2, binary
  circuits, every binary gate type).  The proof wires "the value of a gadget
  computing MAJ_3(x11,x12,x13) instead of x12 and x13", i.e. uses
  MAJ_3(rho, G, G) = G, a special case of weak 1-stability.  The 5 is
  "Since the majority of three bits can be computed in five gates": the size
  of the attached gadget, nothing added.  gates(MAJ_3) over B2 is 4 (WP1 SAT
  ladder, bfs3), so 5 is not tight; why the authors wrote 5 is not stated
  [VERIFY].
- Subadditivity (PDF p.8): both bullets (merge, composition) are required;
  "Clearly, the measures mu(f) = gates(f) and mu_alpha(f) = gates(f) +
  alpha * inputs(f) are subadditive".  Theorem 1 (PDF p.9): subadditive mu,
  any f, weakly m-stable g, every m-substitution rho:
  mu(h) - mu(h|rho) <= m * mu(g).  The proof composes h|rho with a wiring map
  whose outputs are g, g xor 1 or constants; for gates over B2 these cost
  nothing extra (constants and negations are absorbed into gate types: our
  hand argument, stage 1 b4, not in the paper).
- Resolution: none of "gates is not subadditive", "different substitution
  class" or "5 = gates(MAJ_3) + 1 for a structural reason" holds.  The ceiling
  constant is F(g) = gates(g) for weakly 1-stable g; MAJ_3 gives 4, MUX_3
  gives 3.  The paper never instantiates Theorem 1 with mu = gates and m = 1;
  the 3 was left on the table.

Stage 2 (enumeration only, no SAT; per-instance budget 1800 s, 2 cores).
New checker `wp2e_weak1.py`, written from Definition 1 with no code shared
with `stable_check.py` (row-by-row evaluation, returns tau_0 / tau_1
witnesses).  Validation (`log_wp2e_validate.txt`): MAJ_3 accept, MUX_3 accept,
XOR_3 reject, AND_3 reject (exit codes 0, 0, 1, 1); 0 disagreements with
`stable_check.py` weak1 on all 256 tables at k = 3 (32 weakly 1-stable) and
all 65,536 at k = 4 (34,488).  Reductions (pre-registration W1-W3, hand
arguments): a weakly 1-stable g restricted to its essential inputs stays
weakly 1-stable at no larger cost, k essential inputs need >= k - 1 gates, and
WP2d R1-R2 plus invariance under output negation and input permutation make
the WP2d enumerator complete for the question.  Runs (`wp2e_run.py`,
`wp2e_queue.sh`, enumerator `wp2d_enum.enum_dfs` unchanged; `results_wp2e.csv`,
`log_wp2e_main.txt`, `log_wp2e_ext_a.txt`, `log_wp2e_ext_b.txt`; status of every
row: exhaustive; both checkers on every distinct table, 0 disagreements on
all 21 instances):

| (k, s) | structures | distinct functions | weakly 1-stable | of which all inputs essential |
|--------|-----------:|-------------------:|----------------:|------------------------------:|
| (2, 1) | 1     | 5         | 0       | 0       |
| (2, 2) | 2     | 7         | 0       | 0       |
| (3, 2) | 1     | 25        | 0       | 0       |
| (2, 3) | 9     | 8         | 0       | 0       |
| (3, 3) | 9     | 115       | 12      | 12      |
| (4, 3) | 2     | 205       | 32      | 32      |
| (2, 4) | 66    | 8         | 0       | 0       |
| (3, 4) | 85    | 128       | 16      | 16      |
| (4, 4) | 35    | 2,365     | 528     | 528     |
| (5, 4) | 5     | 2,225     | 480     | 480     |
| (2, 5) | 672   | 8         | 0       | 0       |
| (3, 5) | 973   | 128       | 16      | 16      |
| (4, 5) | 538   | 12,140    | 4,904   | 4,856   |
| (5, 5) | 148   | 58,009    | 18,860  | 18,636  |
| (6, 5) | 15    | 29,005    | 7,552   | 7,552   |
| (2, 6) | 8,766 | 8         | 0       | 0       |
| (3, 6) | 13,529 | 128      | 16      | 16      |
| (4, 6) | 8,708 | 28,368    | 13,756  | 13,692  |
| (5, 6) | 3,403 | 845,540   | 399,924 | 394,412 |
| (6, 6) | 672   | 1,399,372 | 516,524 | 511,020 |
| (7, 6) | 52    | 437,025   | 128,800 | 128,800 |

The mandatory instances are s <= 3; s = 4..6 are context and cannot change the
minimum.  Distinct counts at (4, 4), (5, 5), (5, 6), (6, 5), (6, 6), (7, 6)
equal the WP2d main runs.  The (3, 3) hits are 46, 58, 78, 92, 114, 116, 172,
184, 202, 216, 226, 228; 172, 184, 202, 216, 226, 228 are the MUX_3 orbit
under input permutation (with output negation absorbed by the enumerator);
the other six are MUX_3 with one data input negated (up to input
permutation and output negation; checked mechanically).  MUX_3 witness
(`log_wp2e_witness.txt`): `g1 = AND(x1, x2); g2 = NOTAND(x1, x3); g3 = OR(g1, g2)`
from `find_witness`, passes `simulate.py`, both checkers accept; no element of
the MUX_3 orbit lies in E(3, 1) or E(3, 2).  gates(MUX_3) = 3 is also SAT-proven
(WP1, `results_targets.csv`: UNSAT at s = 0, 1, 2, SAT at s = 3) and exhaustive
(bfs3, tt 216 -> 3).  Declared: minimum gates over weakly 1-stable functions on
any number of inputs = 3 (proof status: exhaustive enumeration for the lower
side, verified witness plus SAT for the upper side; the reductions are hand
arguments).

Section 3.2 proof re-derived for MUX_3 (hand argument).  MUX_3(a, b, c) =
a ? b : c.  Let h = f <> MUX_3 in B_3n, rho any 1-substitution x_bp <- rho(z)
(z = the other 3n - 1 variables), without loss of generality b = 1, and H an
optimal circuit for h|rho.  Build C'': keep the input x_1p, add the 3 gates of
G = MUX_3(x11, x12, x13) computed from the inputs, and rewire H:
- p = 1 (select substituted): every edge leaving x12 or x13 now leaves G;
- p = 2: every edge leaving x13 now leaves G; every gate reading x11 gets the
  type obtained by fixing that argument to 0 (the edge is re-pointed to any
  existing node, so the gate keeps in-degree 2 and the count is unchanged);
- p = 3: every edge leaving x12 now leaves G; x11 fixed to 1 in the same way.
No negation is needed in any case (the checker's tau_0 and tau_1 differ only
where tau_0 = 0, tau_1 = 1).  C'' is acyclic (G reads inputs only).  If H's
output node is one of the rewired inputs it becomes G, or a constant for x11,
in which case h itself is constant (below) and gates(h) <= 1.  Correctness:
C'' computes h|rho(z') where z' is z with block 1 rewired; there block 1's
gadget sees the substituted coordinate equal to some bit r = rho(z') and
evaluates to MUX_3(r, G, G) = G (p = 1), MUX_3(0, r, G) = G (p = 2) or
MUX_3(1, G, r) = G (p = 3); the other blocks are untouched; so
h|rho(z') = f(G, MUX_3(x21, x22, x23), ...) = h(x).  Hence
gates(h) <= gates(C'') = gates(h|rho) + 3, i.e.
gates(h) - gates(h|rho) <= 3 for every 1-substitution rho, and also h|rho is
constant only if h is.  With gates(f) <= gates(h) <= gates(f) + 3n (fix
x_i1 = 1, x_i3 = 0 to recover f), Remark 1 of GHKK supplies f, hence h, of
virtually any complexity: an induction step "some 1-substitution removes
>= gain gates from every non-constant function" with gain > 3 is false, so
gate elimination with the gates measure and 1-substitutions cannot prove
better than 3n.  Mechanical check of the functional identity (not of the gate
count; `wp2e_repair_check.py`, `log_wp2e_repair.txt`): wiring taken from the
checker's witnesses, x1 -> x2 = x3 = G, x2 -> x1 = 0, x3 = G, x3 -> x1 = 1,
x2 = G; 0 failures for n = 1 (all f, all rho) and n = 2 (all 16 f, both
blocks, every position, 2000 random rho each; 12,288,000 checks), same for
MAJ_3; a tampered wiring is caught (192 failures, negative control).

Outcome against the pre-registration: P1-P5 hold.  Limits and caveats: the
reductions W1-W3 and the gate-count part of the repair are hand arguments; the
completeness of the enumerator rests on WP2d's controls; this says nothing
about m >= 2, about measures other than gates (the mu_alpha ceiling of the
section at the top stays 7n), or about whether constructions other than
f <> g with a weakly 1-stable g could cap the method below 3n.  This limits a
proof method; it is NOT a circuit lower bound.

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
- `wp2d_enum.py`, `wp2d_struct_count.py`, `wp2d_npn_invariance.py`,
  `wp2d_canon.py`, `wp2d_compare.py` — WP2d: enumerator (two evaluators),
  stand-alone structure counter, R3 test at k = 6, 7, canonical form under input
  permutation, comparison with the reviewer's scripts; `results_wp2d_*.csv`,
  `log_wp2d*.txt`, `wp2d/E_k_s.npy` (my sets), `wp2d/R_k_s.npy` (the reviewer's
  sets, reproduced), `wp2d/C_6_6_*.npy` (canonical forms) — WP2d outputs;
  `wp2d/reviewer_scripts/` — the WP2c reviewer's scripts, verbatim, unreviewed
- `sources/` — transcribed reference values with citations; third-party
  documents are not redistributed (see `sources/SOURCES.md`)

## Setup

```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run_all.py --help
```
