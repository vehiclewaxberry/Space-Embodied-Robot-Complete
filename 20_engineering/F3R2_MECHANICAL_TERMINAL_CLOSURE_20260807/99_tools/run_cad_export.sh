#!/bin/sh
# F3R2 CAD deliverable export.
#
# SolidWorks cannot be driven on this machine (four reproduced failures,
# 05_clearance/G3A_NATIVE_ATTEMPTS.json), so the F3R2 STEP deliverable is
# derived from the hash-bound G2 per-configuration STEP of the SAME assembly
# tree the F3R2 baseline was copied from -- not re-exported from a live
# session, and labelled as such in F3R2_CAD_EXPORT_PROVENANCE.json.
set -e
R2="F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
ST="F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/04_configurations/G2/step"
FC="G:/Windows_program_file/FreeCAD/bin/FreeCADCmd.exe"

SRC="$ST/F3R1_V3_DEPLOYED_NOMINAL.step"
DST="$R2/03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.step"

cp "$SRC" "$DST"
echo "step copied: $(stat -c%s "$DST") bytes"

export F3R2_STEP="$DST"
export F3R2_FCSTD="$R2/03_native_cad/F3R2_SPACE_EMBODIED_ROBOT_OPERATIONAL_BASELINE.FCStd"
"$FC" "$R2/99_tools/fc_make_fcstd.py" > "$R2/99_tools/logs/fc_fcstd.txt" 2>&1
echo "exit=$?"
tr '\r' '\n' < "$R2/99_tools/logs/fc_fcstd.txt" | grep -v '%' | tail -6
