#!/bin/sh
# F3R2 per-solid gripper mesh export. usage: run_gripper_solids.sh <STEP_BASENAME> <TAG>
set -e
R2="F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
ST="F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/04_configurations/G2/step"
FC="G:/Windows_program_file/FreeCAD/bin/FreeCADCmd.exe"
export F3R2_STEP="$ST/$1"
export F3R2_OUTDIR="$R2/05_clearance/mesh/gripper_solids_$2"
export F3R2_PREFIX="B51_REF_gripper_detail_LINKLOCAL"
export F3R2_DEFLECTION="0.25"
"$FC" "$R2/99_tools/fc_export_gripper_solids.py" > "$R2/99_tools/logs/fc_gripper_$2.txt" 2>&1
echo "exit=$?"
tr '\r' '\n' < "$R2/99_tools/logs/fc_gripper_$2.txt" | grep -v '%' | grep -v '^\s*$' | tail -20
