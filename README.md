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
| WP2 | Cheaper m-stable gadgets (tighter ceiling for plain gate elimination, GHKK 2016) | in progress |
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
extracted from a figure of Knuth's draft 7.1.2.

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
- `sources/` — transcribed reference values with citations; third-party
  documents are not redistributed (see `sources/SOURCES.md`)

## Setup

```
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run_all.py --help
```
