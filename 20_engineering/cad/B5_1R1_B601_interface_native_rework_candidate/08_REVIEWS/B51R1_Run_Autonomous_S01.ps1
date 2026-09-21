[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$s01 = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S01'
$sessionId = 'S01'
$priorSessionReceipt = Join-Path $s01 'B51R1_S01_SESSION_EXECUTION_RECEIPT.json'
$priorRecoveryReceipt = Join-Path $s01 'B51R1_SR01_SESSION_EXECUTION_RECEIPT.json'
if (Test-Path -LiteralPath $priorSessionReceipt -PathType Leaf) {
    $prior = Get-Content -Raw -Encoding UTF8 $priorSessionReceipt | ConvertFrom-Json
    if ($prior.status -ne 'S01_FAIL_CLOSED') {
        throw "S01 receipt already exists without a recoverable failure state: $($prior.status)"
    }
    $sessionId = 'SR01'
    if (Test-Path -LiteralPath $priorRecoveryReceipt -PathType Leaf) {
        $priorRecovery = Get-Content -Raw -Encoding UTF8 $priorRecoveryReceipt | ConvertFrom-Json
        if ($priorRecovery.status -ne 'S01_FAIL_CLOSED') {
            throw "SR01 receipt already exists without a recoverable failure state: $($priorRecovery.status)"
        }
        $sessionId = 'SR02'
    }
}
$work = Join-Path $s01 $(if ($sessionId -eq 'S01') {'WORK'} elseif ($sessionId -eq 'SR01') {'WORK_SR01'} else {'WORK_SR02'})
$workTarget = Join-Path $work 'B51R1_MASTER_SKELETON_V2.SLDPRT'
$rawReceipt = Join-Path $s01 "B51R1_${sessionId}_RAW_WORK_BUILD_RECEIPT.json"
$gateReceipt = Join-Path $s01 'B51R1_S01_GATE_RECEIPT.json'
$sessionReceipt = Join-Path $s01 "B51R1_${sessionId}_SESSION_EXECUTION_RECEIPT.json"
$target = Join-Path $root '02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2.SLDPRT'
$stageA = Join-Path $root '02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT'
$g1b = Join-Path $root '09_DELIVERY\B51R1_AUTONOMOUS_G1A_CLOSURE_20260801\B51R1_G1B_STANDING_SESSION_ADMISSION.json'
$finalLock = Join-Path $root '09_DELIVERY\B51R1_AUTONOMOUS_G1A_CLOSURE_20260801\B51R1_PHASE2A_INPUT_LOCK_V3_FINAL.json'
$ledgerPath = Join-Path $root '09_DELIVERY\B51R1_AUTONOMOUS_G1A_CLOSURE_20260801\B51R1_AUTONOMOUS_SESSION_POOL_LEDGER.json'
$builder = Join-Path $root '02_MASTER_SKELETON\B51R1_MasterSkeletonNativeBuilder.dll'
$finalizer = Join-Path $PSScriptRoot 'B51R1_S01_MasterSkeletonFinalizer.dll'
$interop = 'F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll'
$solidworksExe = 'F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe'
$expectedG1b = 'FF33C4FEC8B48C0B759C2BB9E6EA202E89B10DC4789B6385FC15841338276EE6'
$expectedLock = 'AE4FF6021E837651CA019B7ABE8E84B4D0F92183CF158312DF7F826871A3F214'
$expectedStageA = '5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B'

function Get-Sha([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

foreach ($path in @($g1b, $finalLock, $ledgerPath, $builder, $finalizer, $interop, $solidworksExe, $stageA)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "S01 required input missing: $path"
    }
}
if ((Get-Sha $g1b) -ne $expectedG1b) { throw 'G1B receipt hash mismatch' }
if ((Get-Sha $finalLock) -ne $expectedLock) { throw 'Final V3 input lock hash mismatch' }
if ((Get-Sha $stageA) -ne $expectedStageA) { throw 'Protected Stage A hash mismatch before launch' }
if (Test-Path -LiteralPath $target) { throw "Final target exists; refusing overwrite: $target" }
if (Test-Path -LiteralPath $work) { throw "S01 work directory exists; refusing ambiguous rerun: $work" }
$existing = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
if ($existing.Count -ne 0) { throw "Expected zero SLDWORKS processes before S01; found $($existing.Count)" }

$utf8NoBom = New-Object Text.UTF8Encoding($false)
$ledger = Get-Content -Raw -Encoding UTF8 $ledgerPath | ConvertFrom-Json
if ($ledger.status -ne 'ACTIVE_G1B_STANDING_SESSION_POOL' -or $ledger.remaining -lt 1) {
    throw 'Standing session pool is not active or has no remaining launch'
}
if ($null -eq $ledger.PSObject.Properties['entries']) {
    $ledger | Add-Member -NotePropertyName entries -NotePropertyValue @()
}
foreach ($priorSpec in @(
    [pscustomobject]@{id='S01'; path=$priorSessionReceipt; next='SR01_DIRECT_EXECUTABLE_ROT_ATTACH'},
    [pscustomobject]@{id='SR01'; path=$priorRecoveryReceipt; next='SR02_CSHARP_INTERNAL_ROT_ATTACH'}
)) {
    if ((Test-Path -LiteralPath $priorSpec.path -PathType Leaf) -and
        @($ledger.entries | Where-Object { $_.session_id -eq $priorSpec.id }).Count -eq 0) {
        $prior = Get-Content -Raw -Encoding UTF8 $priorSpec.path | ConvertFrom-Json
        $ledger.entries = @($ledger.entries) + @([pscustomobject]@{
            session_id = $priorSpec.id
            started_at = $prior.started_at
            completed_at = $prior.completed_at
            status = $prior.status
            process_id = $(if ($null -ne $prior.PSObject.Properties['process_id']) {$prior.process_id} else {$null})
            receipt_path = "07_VERIFICATION/AUTONOMOUS/S01/B51R1_$($priorSpec.id)_SESSION_EXECUTION_RECEIPT.json"
            gate_receipt_path = $null
            recovery_disposition = $priorSpec.next
        })
    }
}
$ledger.consumed_since_activation = @($ledger.entries).Count
$ledger.remaining = [int]$ledger.budget - [int]$ledger.consumed_since_activation
if (@($ledger.entries | Where-Object { $_.session_id -eq $sessionId }).Count -ne 0) {
    throw "$sessionId session ID already present in ledger"
}
[IO.File]::WriteAllText($ledgerPath, ($ledger | ConvertTo-Json -Depth 10) + "`n", $utf8NoBom)

New-Item -ItemType Directory -Path $work -Force | Out-Null
$started = [DateTimeOffset]::Now.ToString('o')
$session = [ordered]@{
    schema = 'B51R1_S01_SESSION_EXECUTION_RECEIPT_V1'
    session_id = $sessionId
    started_at = $started
    status = 'FAIL_CLOSED_NOT_STARTED'
    g1b_sha256 = $expectedG1b
    input_lock_sha256 = $expectedLock
    protected_stage_a_sha256_before = $expectedStageA
    raw_builder_sha256 = Get-Sha $builder
    finalizer_dll_sha256 = Get-Sha $finalizer
    finalizer_source_sha256 = Get-Sha (Join-Path $PSScriptRoot 'B51R1_S01_MasterSkeletonFinalizer.cs')
    runner_sha256 = Get-Sha $PSCommandPath
    visible = $true
    primary_goal = 'CREATE_FINAL_MASTER_SKELETON'
}
$app = $null
$processId = $null
$exitCode = 1
try {
    [void][Reflection.Assembly]::LoadFrom($interop)
    [void][Reflection.Assembly]::LoadFrom($builder)
    [void][Reflection.Assembly]::LoadFrom($finalizer)

    $launched = Start-Process -FilePath $solidworksExe -PassThru
    $processId = $launched.Id
    $process = $null
    for ($i = 0; $i -lt 60; $i++) {
        Start-Sleep -Milliseconds 500
        $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($null -ne $process -and $process.Responding -and $process.MainWindowHandle -ne 0) { break }
    }
    if ($null -eq $process -or -not $process.Responding -or $process.MainWindowHandle -eq 0) {
        throw 'SolidWorks visible responsive main window did not appear within 30 seconds'
    }
    $processes = @(Get-Process -Name SLDWORKS -ErrorAction Stop)
    if ($processes.Count -ne 1) { throw "Expected one SLDWORKS process after launch; found $($processes.Count)" }
    if ($processes[0].Id -ne $processId) { throw "ROT process identity differs from launched PID $processId" }
    if (-not $processes[0].Responding) { throw 'Authorized SLDWORKS process is not responding after launch' }
    $session['process_id'] = $processId
    $session['solidworks_revision'] = (Get-Item -LiteralPath $solidworksExe).VersionInfo.ProductVersion
    $session['attachment_route'] = 'DIRECT_EXECUTABLE_VISIBLE_THEN_CSHARP_INTERNAL_MARSHAL_GETACTIVEOBJECT'

    $raw = [B51R1MasterSkeletonNativeBuilder]::Run($workTarget, $rawReceipt)
    $session['raw_builder_result'] = $raw
    if ($raw -ne 0 -or -not (Test-Path -LiteralPath $workTarget -PathType Leaf)) {
        throw "Isolated raw skeleton build failed with code $raw"
    }
    $final = [B51R1S01MasterSkeletonFinalizer]::Run(
        $workTarget,
        $target,
        $gateReceipt,
        $g1b,
        $expectedG1b,
        $finalLock,
        $expectedLock,
        $stageA,
        $expectedStageA
    )
    $session['finalizer_result'] = $final
    if ($final -ne 0 -or -not (Test-Path -LiteralPath $target -PathType Leaf)) {
        throw "S01 native finalizer failed with code $final"
    }
    $gate = Get-Content -Raw -Encoding UTF8 $gateReceipt | ConvertFrom-Json
    if ($gate.status -ne 'S01_PASS_NATIVE_MASTER_SKELETON_CREATED') {
        throw "S01 gate receipt did not pass: $($gate.status)"
    }
    if ((Get-Sha $stageA) -ne $expectedStageA) { throw 'Protected Stage A hash changed during S01' }
    $session['status'] = 'S01_PASS_NATIVE_MASTER_SKELETON_CREATED'
    $session['target_bytes'] = (Get-Item -LiteralPath $target).Length
    $session['target_sha256'] = Get-Sha $target
    $session['gate_receipt_sha256'] = Get-Sha $gateReceipt
    $exitCode = 0
}
catch {
    $session['status'] = 'S01_FAIL_CLOSED'
    $session['error_type'] = $_.Exception.GetType().FullName
    $session['error_message'] = $_.Exception.Message
    $exitCode = 1
}
finally {
    $session['completed_at'] = [DateTimeOffset]::Now.ToString('o')
    if ($null -ne $processId) {
        $exactProcess = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($null -ne $exactProcess -and $exactProcess.Responding) {
            try { [void]$exactProcess.CloseMainWindow() } catch { }
        }
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    for ($i = 0; $i -lt 40; $i++) {
        if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -eq 0) { break }
        Start-Sleep -Milliseconds 500
    }
    $remainingProcesses = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
    $session['normal_application_exit'] = ($remainingProcesses.Count -eq 0)
    $session['protected_stage_a_sha256_after'] = Get-Sha $stageA
    $session['final_target_exists'] = Test-Path -LiteralPath $target -PathType Leaf
    [IO.File]::WriteAllText($sessionReceipt, ($session | ConvertTo-Json -Depth 8) + "`n", $utf8NoBom)

    $ledger = Get-Content -Raw -Encoding UTF8 $ledgerPath | ConvertFrom-Json
    $event = [pscustomobject]@{
        session_id = $sessionId
        started_at = $started
        completed_at = $session['completed_at']
        status = $session['status']
        process_id = $processId
        receipt_path = "07_VERIFICATION/AUTONOMOUS/S01/B51R1_${sessionId}_SESSION_EXECUTION_RECEIPT.json"
        gate_receipt_path = '07_VERIFICATION/AUTONOMOUS/S01/B51R1_S01_GATE_RECEIPT.json'
    }
    $ledger.entries = @($ledger.entries) + @($event)
    $ledger.consumed_since_activation = [int]$ledger.consumed_since_activation + 1
    $ledger.remaining = [int]$ledger.budget - [int]$ledger.consumed_since_activation
    foreach ($property in @('last_session_id','last_session_status','updated_at')) {
        if ($null -eq $ledger.PSObject.Properties[$property]) {
            $ledger | Add-Member -NotePropertyName $property -NotePropertyValue $null
        }
    }
    $ledger.last_session_id = $sessionId
    $ledger.last_session_status = $session['status']
    $ledger.updated_at = [DateTimeOffset]::Now.ToString('o')
    [IO.File]::WriteAllText($ledgerPath, ($ledger | ConvertTo-Json -Depth 10) + "`n", $utf8NoBom)
}

$session | ConvertTo-Json -Depth 8
exit $exitCode
