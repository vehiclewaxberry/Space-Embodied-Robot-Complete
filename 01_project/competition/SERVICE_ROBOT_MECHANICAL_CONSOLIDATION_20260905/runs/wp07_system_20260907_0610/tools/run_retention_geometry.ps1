$ErrorActionPreference = 'Stop'
$taskPython = 'G:/Windows_program_file/Anaconda/python.exe'
$taskRun = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $taskRun
if (Test-Path -LiteralPath 'results/retention_detail/station_1/EMISSION_RECEIPT.json') { throw 'Station 1 already exists; preserve it and run only missing checks.' }
& $taskPython -X utf8 run_guard.py --timeout 180 retention_gen1_c02 -- $taskPython -X utf8 candidate/retention_detail.py --station 1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$taskFailures = @()
foreach ($station in @(0, 1)) {
    if ($station -eq 1) {
        & $taskPython -X utf8 run_guard.py --timeout 240 retention_local1_c03 -- $taskPython -X utf8 tools/check_retention_detail_c03.py --station 1 --mode local
        if ($LASTEXITCODE -ne 0) { $taskFailures += 'local1' }
        $guardRecord = Get-Content -LiteralPath 'logs/retention_local1_c03.run.json' -Raw | ConvertFrom-Json
        if ($guardRecord.status -notin @('COMPLETED', 'COMMAND_FAILED')) { exit 3 }
    }
    foreach ($state in @('parking', 'service', 'released')) {
        $jobName = 'retention_neighbours' + $station + '_' + $state + '_c03'
        & $taskPython -X utf8 run_guard.py --timeout 240 $jobName -- $taskPython -X utf8 tools/check_retention_detail_c03.py --station $station --mode neighbours --state $state
        if ($LASTEXITCODE -ne 0) { $taskFailures += $jobName }
        $guardPath = 'logs/' + $jobName + '.run.json'
        $guardRecord = Get-Content -LiteralPath $guardPath -Raw | ConvertFrom-Json
        if ($guardRecord.status -notin @('COMPLETED', 'COMMAND_FAILED')) { exit 3 }
    }
}
if ($taskFailures.Count -gt 0) { $taskFailures | ConvertTo-Json -Compress; exit 2 }
exit 0
