$ErrorActionPreference = 'Stop'
$taskPython = 'G:/Windows_program_file/Anaconda/python.exe'
$taskRun = Split-Path -Parent $PSScriptRoot
$cadTools = 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts'
Set-Location -LiteralPath $taskRun
$targets = @(
    @{name='retention_view0'; file='candidate/retention_station0.step.py'},
    @{name='retention_view1'; file='candidate/retention_station1.step.py'},
    @{name='pcb_reference'; file='candidate/pcb_reference_panels.step.py'}
)
foreach ($target in $targets) {
    & $taskPython -X utf8 run_guard.py --timeout 240 ('gen_' + $target.name) -- $taskPython -X utf8 ($cadTools + '/gen') $target.file --write --json
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $taskPython -X utf8 run_guard.py --timeout 150 ('refs_' + $target.name) -- $taskPython -X utf8 ($cadTools + '/inspect') refs $target.file --facts --planes --positioning
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $taskPython -X utf8 run_guard.py --timeout 150 ('validate_' + $target.name) -- $taskPython -X utf8 ($cadTools + '/inspect') validate $target.file
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
& $taskPython -X utf8 run_guard.py --timeout 180 pcb_step_readback -- $taskPython -X utf8 tools/check_pcb_step_readback.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
foreach ($station in @(0, 1)) {
    $neutralPath = 'native/RET_S' + $station + '_c03_v1/local_assembly_roundtrip.step'
    & $taskPython -X utf8 run_guard.py --timeout 150 ('validate_native_retention' + $station) -- $taskPython -X utf8 ($cadTools + '/inspect') validate $neutralPath
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
exit 0
