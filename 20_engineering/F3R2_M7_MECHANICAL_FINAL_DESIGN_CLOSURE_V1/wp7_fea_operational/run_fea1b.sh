#!/bin/sh
# FEA-1B batch runner -- M7 / WP7. ONE JOB AT A TIME, batch only, no CAE GUI.
# usage: sh run_fea1b.sh <pattern>
HERE="f:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/F3R2_M7_MECHANICAL_FINAL_DESIGN_CLOSURE_V1/wp7_fea_operational"
ABQ="D:/SIMULIA/Commands/abaqus.bat"
PAT="$1"
cd "$HERE/jobs_b" || exit 1
for f in "$HERE"/decks_b/*"$PAT"*.inp; do
  j=$(basename "$f" .inp)
  if [ -f "$j.odb" ] && [ -f "$j.sta" ]; then
    if grep -q "COMPLETED SUCCESSFULLY" "$j.sta" 2>/dev/null; then
      echo "SKIP(done) $j"; continue
    fi
  fi
  cp "$f" .
  t0=$(date +%s)
  "$ABQ" job="$j" interactive > "$j.runlog" 2>&1
  rc=$?
  t1=$(date +%s)
  st=$(grep -c "COMPLETED SUCCESSFULLY" "$j.sta" 2>/dev/null || echo 0)
  echo "$j rc=$rc wall=$((t1-t0))s completed_flag=$st"
done
