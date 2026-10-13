Superseded WP3.2 result files and run logs, kept as the record of the
post-freeze fixes (pre-registration P9). None of these numbers is reported as a
result; the reported results are in ../wp32/ (final code, commit after fix 7).

stageB_code/                 first runs with the stage-B encoder (before fix 1)
run_controls_fix1.txt        controls re-run after fix 1 (14/14 replayed violations)
run_controls_fix2.txt        controls re-run after fix 2 (13 violations; m_dropped_pre_4 spurious)
run_controls_fix3.txt        controls re-run after fix 3 (14/14 replayed violations)
run_controls_fix4_symbolic_const.txt  after the hidden-input refactor (fix 4) with symbolic
                             trivialising constants (m_weakened_pattern_4 spurious: the
                             other constant is vacuous in the engine)
run_controls_fix4_light.txt  after fix 4 with forward-only simulation of the other
                             constant (14/14 replayed violations)
*.json, run_leaves.txt, run_controls_internal.txt (top)
                             runs with commit 47449a0 (before fix 4: unsound small-pool
                             semantics, stopped)
pre_fix6/                    runs after fix 5, before fix 6 (controls 14/14)
pre_fix7/                    runs after fix 6, before fix 7
