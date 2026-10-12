# Reference sources (not redistributed)

Downloaded locally on 2026-10-11; excluded from the repo for copyright reasons.
Transcribed values with page/table citations are in TRANSCRIPTION_2026-10-11.txt
(frozen, sha256 in ../targets_frozen.stamp); corrections in ERRATA.txt.

- Knuth, TAOCP Vol. 4 pre-fascicle 0C (Section 7.1.2, Boolean evaluation), draft:
  https://www-cs-faculty.stanford.edu/~knuth/fasc0c.ps.gz  — text extracted with ps2txt.py
- Kulikov, Pechenev, Slezkin, "SAT-based Circuit Local Improvement", arXiv:2102.12579v3:
  https://arxiv.org/abs/2102.12579

WP2 (added 2026-10-11):

- Golovnev, Hirsch, Knop, Kulikov, "On the Limits of Gate Elimination". Journal version
  (JCSS 2018; preliminary version MFCS 2016, LIPIcs 58, 46:1-46:13; ECCC TR16-119,
  https://eccc.weizmann.ac.il/report/2016/119/). PDF fetched from
  https://golovnev.org/papers/limits.pdf (20 pages, sha256
  fb0b1b2b4b18036f72a39cfc55a3e47512a5bb69e6195ce3abc23f3f80428e03), stored locally as
  ghkk-limits.pdf with the pypdf text extraction ghkk-limits.txt (both excluded from the
  repo). Definitions 1-2, Theorems 1 and 4, Lemma 4 (truth table of gst1), Corollary 6
  and the two Appendix A scripts are transcribed with page references in
  GHKK_TRANSCRIPTION_2026-10-11.txt (frozen, sha256 in ../wp2_frozen.stamp).

WP2b (added 2026-10-11):

- Goucher, A. P., `optimal5`: database of Knuth's optimal chains for all 616,126 NPN classes
  of 5-input Boolean functions, with lookup code. https://gitlab.com/apgoucher/optimal5,
  git commit b7668d77d7e57d504c19e4cf4884d9e2d0991d88 (2020-03-20, "Avoid TBAA violation
  and fix various warnings"). Licence: MIT (LICENCE.txt, "Copyright 2019 Adam P. Goucher").
  Cloned read-only at /tmp/optimal5 and NOT copied into this repository; only the data file
  is read: knuthies.dat, 9,241,860 bytes = 616,124 records of 15 bytes, sha256
  0cac5ce6aba0ce348b1d4b98845206333fe8c3d9a1b783271ac18e8bfa6a1c0f (recorded in
  ../wp2b_frozen.stamp). The record format and the truth-table convention were read from
  optimal5.h (bytes2gv, load_chains, the calcs vector 0x0000ffff, 0x00ff00ff, 0x0f0f0f0f,
  0x33333333, 0x55555555) and are re-implemented in ../optimal5_glue.py because no C++
  compiler is available on the host. The published reference histogram (classes and
  functions per cost, "Table agrees with chapter 7.1.2 of Knuth") is checktab.py in that
  repository; it is reproduced verbatim in ../wp2b_run.py (KNUTH_CLASSES, KNUTH_FUNCS) and
  compared cell by cell in ../results_wp2b_knuth_hist.csv.
- The optimal chains themselves are Knuth's (TAOCP Vol. 4A Section 7.1.2, program
  BOOLCHAINS, https://www-cs-faculty.stanford.edu/~knuth/programs.html), as packaged by
  optimal5; they are used as given and are not re-verified here beyond the histogram and
  the cross-checks listed in ../results_wp2b_crosscheck.csv.

WP3.1 (added 2026-10-12):

- Find, Golovnev, Hirsch, Kulikov, "Improving 3n Circuit Complexity Lower Bounds",
  ECCC TR15-166, Revision 2 (August 16, 2022),
  https://eccc.weizmann.ac.il/report/2015/166/revision/2/download, 44 pages, sha256
  9393c685b07682dc01ae0888450ed4475b774ea9e0e2b8d491cecf4a29ee0404, stored locally as
  fghk-r2.pdf with the pypdf text extraction fghk-r2.txt (both excluded from the repo).
  The circuit model, measure, normalization rules, substitution types and Cases 1-5 are
  transcribed with page references in ../wp3/wp31_preregistration_2026-10-12.txt (frozen,
  sha256 in ../wp3/wp31_frozen.stamp).
