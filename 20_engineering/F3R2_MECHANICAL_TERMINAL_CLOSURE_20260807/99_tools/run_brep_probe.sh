#!/bin/sh
# F3R2 B-rep probe driver. usage: run_brep_probe.sh <STEP_BASENAME> <TAG> <PART_PREFIXES>
set -e
R2="F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
ST="F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/04_configurations/G2/step"
FC="G:/Windows_program_file/FreeCAD/bin/FreeCADCmd.exe"
export F3R2_STEP="$ST/$1"
export F3R2_OUT="$R2/05_clearance/mesh/BREP_PROBE_$2.json"
export F3R2_PARTS="$3"
"$FC" "$R2/99_tools/fc_probe_brep.py" > "$R2/99_tools/logs/fc_brep_$2.txt" 2>&1
echo "exit=$?"
tr '\r' '\n' < "$R2/99_tools/logs/fc_brep_$2.txt" | grep -v '%' | grep -v '^\s*$' | tail -25
