#!/bin/sh
# F3R2 STEP structure probe driver.  usage: run_probe.sh <STEP_BASENAME> <TAG>
set -e
R2="F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/F3R2_MECHANICAL_TERMINAL_CLOSURE_20260807"
ST="F:/China Graduate Future Flight Vehicle Innovation Competition/20_engineering/F3R1_MECHANICAL_INTEGRATION_RECOVERY_20260806/04_configurations/G2/step"
FC="G:/Windows_program_file/FreeCAD/bin/FreeCADCmd.exe"
export F3R2_STEP="$ST/$1"
export F3R2_OUT="$R2/05_clearance/mesh/STEP_PROBE_$2.json"
"$FC" "$R2/99_tools/fc_probe_step.py" > "$R2/99_tools/logs/fc_probe_$2.txt" 2>&1
echo "exit=$?"
tr '\r' '\n' < "$R2/99_tools/logs/fc_probe_$2.txt" | grep -v '%' | head -8
