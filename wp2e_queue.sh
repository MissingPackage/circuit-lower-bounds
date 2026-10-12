#!/bin/bash
# usage: queue.sh LOG "k s" "k s" ...
cd "$(dirname "$0")"
P=.venv/bin/python
LOG=$1; shift
for ks in "$@"; do
  set -- $ks
  echo "=== start ($1,$2) $(date -u +%H:%M:%S)" >> $LOG
  timeout 1800 $P wp2e_run.py instance --k $1 --s $2 >> $LOG 2>&1
  rc=$?
  if [ $rc -eq 124 ]; then $P wp2e_run.py timeout --k $1 --s $2 --budget 1800; echo "($1,$2) TIMEOUT 1800 s" >> $LOG; fi
  echo "=== end ($1,$2) rc=$rc $(date -u +%H:%M:%S)" >> $LOG
done
