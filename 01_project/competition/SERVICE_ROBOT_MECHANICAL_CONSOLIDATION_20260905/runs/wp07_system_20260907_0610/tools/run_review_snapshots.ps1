$ErrorActionPreference = 'Stop'
$taskPython = 'G:/Windows_program_file/Anaconda/python.exe'
$taskRun = Split-Path -Parent $PSScriptRoot
$snapshotTool = 'F:/codex_skill/AgentSkills/codex-skills/cad/scripts/snapshot'
Set-Location -LiteralPath $taskRun
foreach ($name in @('SERVICE', 'RETENTION0', 'RETENTION1', 'PCB_REFERENCE')) {
    $job = 'inputs/SNAPSHOT_' + $name + '.json'
    & $taskPython -X utf8 run_guard.py --timeout 180 ('snapshot_' + $name.ToLower()) -- $taskPython -X utf8 $snapshotTool --job $job --json
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
exit 0
