[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$s01 = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S01'
$sessionId = 'SR03'
$expectedProcessId = 48160
$work = Join-Path $s01 'WORK_SR03'
$workTarget = Join-Path $work 'B51R1_MASTER_SKELETON_V2.SLDPRT'
$rawReceipt = Join-Path $s01 'B51R1_SR03_RAW_WORK_BUILD_RECEIPT.json'
$rawProgress = Join-Path $s01 'B51R1_SR03_RAW_WORK_BUILD_RECEIPT_PROGRESS.log'
$probeReceipt = Join-Path $s01 'B51R1_SR03_EXISTING_SOLIDWORKS_PROBE_RECEIPT.json'
$gateReceipt = Join-Path $s01 'B51R1_S01_GATE_RECEIPT_SR03_SUPERSESSION.json'
$sessionReceipt = Join-Path $s01 'B51R1_SR03_SESSION_EXECUTION_RECEIPT.json'
$target = Join-Path $root '02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2.SLDPRT'
$stageA = Join-Path $root '02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT'
$g1b = Join-Path $root '09_DELIVERY\B51R1_AUTONOMOUS_G1A_CLOSURE_20260801\B51R1_G1B_STANDING_SESSION_ADMISSION.json'
$finalLock = Join-Path $root '09_DELIVERY\B51R1_AUTONOMOUS_G1A_CLOSURE_20260801\B51R1_PHASE2A_INPUT_LOCK_V3_FINAL.json'
$ledgerPath = Join-Path $root '09_DELIVERY\B51R1_AUTONOMOUS_G1A_CLOSURE_20260801\B51R1_AUTONOMOUS_SESSION_POOL_LEDGER.json'
$authorization = Join-Path $s01 'B51R1_SR03_USER_RECOVERY_REOPEN_AUTHORIZATION.json'
$admissionAddendum = Join-Path $s01 'B51R1_SR03_ADMISSION_ADDENDUM.json'
$oldHold = Join-Path $s01 'B51R1_S01_GATE_RECEIPT.json'
$incident = Join-Path $s01 'B51R1_S01_AUTOMATIC_STOP_INCIDENT.json'
$builder = Join-Path $root '02_MASTER_SKELETON\B51R1_MasterSkeletonNativeBuilder.dll'
$builderSource = Join-Path $root '02_MASTER_SKELETON\B51R1_MasterSkeletonNativeBuilder.cs'
$finalizer = Join-Path $PSScriptRoot 'B51R1_S01_MasterSkeletonFinalizer.dll'
$finalizerSource = Join-Path $PSScriptRoot 'B51R1_S01_MasterSkeletonFinalizer.cs'
$probe = Join-Path $PSScriptRoot 'B51R1_SR03_ExistingSolidWorksProbe.dll'
$probeSource = Join-Path $PSScriptRoot 'B51R1_SR03_ExistingSolidWorksProbe.cs'
$interop = 'F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll'
$solidworksExe = 'F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe'

$expectedG1b = 'FF33C4FEC8B48C0B759C2BB9E6EA202E89B10DC4789B6385FC15841338276EE6'
$expectedLock = 'AE4FF6021E837651CA019B7ABE8E84B4D0F92183CF158312DF7F826871A3F214'
$expectedStageA = '5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B'
$expectedAuthorization = '6516F04FA1A23EA686F948DCEFA7627CC3205F684649CE2910E3BDEB35D3B342'
$expectedAdmissionAddendum = '1CE467BD473ACE1E0F7C3356E683C4B59755D8A26739F9348918537D57E30619'
$expectedOldHold = 'DF31F5A674E093F7BF4F6CCDCDBC3DE9ACD3B9DA76992D0E2155620C6DB10E74'
$expectedIncident = 'E1C9D45C33DCF2500445A180B79CFF7A54F6D9EC5841A35DB15509D09E279A10'
$expectedSolidworksExe = '4F4B5A8A3706831B65D871BD1549D98CD6F7AA4EEEF17D15873801A7A1668E60'
$expectedBuilder = 'D24B28D6BBF056213D5A7A97AEF0A2EFD8CAFEE8DCE3047B43EBF102A64F4EAF'
$expectedBuilderSource = '035B57437C804E90E9A685BDDEFC8D8BC525683AD83A0138383A6BA21940C185'
$expectedFinalizer = '7AE33025638F38AEBCAF8A68B3F23DED91080BF4C098364FB06EE9F31EE08978'
$expectedFinalizerSource = '3537CC90D61054BB54B18F6243ADA0B568AF8A9403933066B7C0C704F624D686'
$expectedProbe = 'DA43236D0F591219F18D3D5EF387F85BD47A1C89C4110A8F091950F47B43D8C2'
$expectedProbeSource = '643F065206CAF7AEA6F663B5CB03E1F32A35BE57FFFBC380ADD4278D38D89BC3'

function Get-Sha([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Assert-Hash([string]$Path, [string]$Expected, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label missing: $Path"
    }
    $observed = Get-Sha $Path
    if ($observed -ne $Expected) {
        throw "$Label hash mismatch: expected=$Expected observed=$observed"
    }
}

Assert-Hash $g1b $expectedG1b 'G1B receipt'
Assert-Hash $finalLock $expectedLock 'Final V3 input lock'
Assert-Hash $stageA $expectedStageA 'Protected Stage A'
Assert-Hash $authorization $expectedAuthorization 'SR03 user authorization'
Assert-Hash $admissionAddendum $expectedAdmissionAddendum 'SR03 admission addendum'
Assert-Hash $oldHold $expectedOldHold 'Immutable S01 HOLD receipt'
Assert-Hash $incident $expectedIncident 'Immutable automatic-stop incident'
Assert-Hash $solidworksExe $expectedSolidworksExe 'SolidWorks executable'
Assert-Hash $builder $expectedBuilder 'Raw builder DLL'
Assert-Hash $builderSource $expectedBuilderSource 'Raw builder source'
Assert-Hash $finalizer $expectedFinalizer 'Finalizer DLL'
Assert-Hash $finalizerSource $expectedFinalizerSource 'Finalizer source'
Assert-Hash $probe $expectedProbe 'Existing-session probe DLL'
Assert-Hash $probeSource $expectedProbeSource 'Existing-session probe source'
if (-not (Test-Path -LiteralPath $interop -PathType Leaf)) { throw 'SolidWorks interop DLL missing' }

foreach ($mustBeAbsent in @(
    $target,
    $work,
    $rawReceipt,
    $rawProgress,
    $probeReceipt,
    $gateReceipt,
    $sessionReceipt
)) {
    if (Test-Path -LiteralPath $mustBeAbsent) {
        throw "SR03 output already exists; refusing ambiguous rerun: $mustBeAbsent"
    }
}

$existing = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
if ($existing.Count -ne 1) { throw "Expected exactly one existing SLDWORKS process; found $($existing.Count)" }
$authorizedProcess = $existing[0]
if ($authorizedProcess.Id -ne $expectedProcessId) { throw "Expected PID $expectedProcessId; found $($authorizedProcess.Id)" }
if (-not $authorizedProcess.Responding) { throw 'Authorized SLDWORKS process is not responding' }
if ($authorizedProcess.MainWindowHandle -eq 0) { throw 'Authorized SLDWORKS process has no visible main window' }
if ((Get-Sha $authorizedProcess.Path) -ne $expectedSolidworksExe) { throw 'Authorized SLDWORKS executable hash mismatch' }

$ledger = Get-Content -Raw -Encoding UTF8 -LiteralPath $ledgerPath | ConvertFrom-Json
if ($ledger.status -ne 'ACTIVE_USER_REOPENED_SINGLE_S01_RECOVERY_SLOT') { throw "Ledger not in SR03 authorization state: $($ledger.status)" }
if ([int]$ledger.consumed_since_activation -ne 3 -or [int]$ledger.remaining -ne 17) { throw 'Unexpected pre-SR03 budget state' }
if (-not [bool]$ledger.next_session_authorized -or $ledger.next_session_id -ne $sessionId) { throw 'Ledger does not authorize only SR03' }
if ($ledger.authorized_recovery_slot.session_id -ne $sessionId -or [int]$ledger.authorized_recovery_slot.remaining_attempts -ne 1) { throw 'SR03 recovery slot is not available' }
if ($ledger.user_recovery_reopen_authorization.sha256 -ne $expectedAuthorization) { throw 'Ledger authorization hash mismatch' }
if (@($ledger.entries | Where-Object { $_.session_id -eq $sessionId }).Count -ne 0) { throw 'SR03 ledger entry already exists' }

$utf8NoBom = New-Object Text.UTF8Encoding($false)
New-Item -ItemType Directory -Path $work | Out-Null
$started = [DateTimeOffset]::Now.ToString('o')
$session = [ordered]@{
    schema = 'B51R1_SR03_SESSION_EXECUTION_RECEIPT_V1'
    session_id = $sessionId
    gate = 'S01'
    started_at = $started
    status = 'FAIL_CLOSED_NOT_STARTED'
    process_id = $expectedProcessId
    visible = $true
    launch_new_solidworks_process = $false
    attachment_route = 'EXISTING_USER_OPENED_VISIBLE_PROCESS_CSHARP_INTERNAL_ROT_ATTACH'
    authorization_sha256 = $expectedAuthorization
    admission_addendum_sha256 = $expectedAdmissionAddendum
    g1b_sha256 = $expectedG1b
    input_lock_sha256 = $expectedLock
    protected_stage_a_sha256_before = $expectedStageA
    immutable_hold_receipt_sha256_before = $expectedOldHold
    automatic_stop_incident_sha256_before = $expectedIncident
    solidworks_executable_sha256 = $expectedSolidworksExe
    raw_builder_dll_sha256 = $expectedBuilder
    raw_builder_source_sha256 = $expectedBuilderSource
    finalizer_dll_sha256 = $expectedFinalizer
    finalizer_source_sha256 = $expectedFinalizerSource
    probe_dll_sha256 = $expectedProbe
    probe_source_sha256 = $expectedProbeSource
    runner_sha256 = Get-Sha $PSCommandPath
    primary_goal = 'CREATE_FINAL_NATIVE_MASTER_SKELETON_WITHOUT_OVERWRITING_PRIOR_HOLD'
}
$exitCode = 1
try {
    [void][Reflection.Assembly]::LoadFrom($interop)
    [void][Reflection.Assembly]::LoadFrom($probe)
    [void][Reflection.Assembly]::LoadFrom($builder)
    [void][Reflection.Assembly]::LoadFrom($finalizer)

    $probeResult = [B51R1SR03ExistingSolidWorksProbe]::Run($expectedProcessId, $probeReceipt)
    $session['probe_result'] = $probeResult
    if ($probeResult -ne 0) { throw "Existing SolidWorks session probe failed with code $probeResult" }
    $probeData = Get-Content -Raw -Encoding UTF8 -LiteralPath $probeReceipt | ConvertFrom-Json
    if ($probeData.status -ne 'PASS_EXISTING_SINGLE_VISIBLE_RESPONSIVE_DOCUMENT_EMPTY_SESSION') {
        throw "Existing SolidWorks session probe did not pass: $($probeData.status)"
    }
    $session['probe_receipt_sha256'] = Get-Sha $probeReceipt

    $processes = @(Get-Process -Name SLDWORKS -ErrorAction Stop)
    if ($processes.Count -ne 1 -or $processes[0].Id -ne $expectedProcessId -or -not $processes[0].Responding) {
        throw 'SolidWorks process identity or responsiveness changed after probe'
    }

    $rawResult = [B51R1MasterSkeletonNativeBuilder]::Run($workTarget, $rawReceipt)
    $session['raw_builder_result'] = $rawResult
    if ($rawResult -ne 0 -or -not (Test-Path -LiteralPath $workTarget -PathType Leaf)) {
        throw "Isolated raw skeleton build failed with code $rawResult"
    }
    $rawData = Get-Content -Raw -Encoding UTF8 -LiteralPath $rawReceipt | ConvertFrom-Json
    if ($rawData.status -ne 'PASS_NATIVE_MASTER_SKELETON_BUILT') {
        throw "Raw builder receipt did not pass: $($rawData.status)"
    }
    $session['raw_receipt_sha256'] = Get-Sha $rawReceipt
    $session['raw_progress_sha256'] = Get-Sha $rawProgress
    $session['work_target_bytes'] = (Get-Item -LiteralPath $workTarget).Length
    $session['work_target_sha256'] = Get-Sha $workTarget

    if (Test-Path -LiteralPath $target) { throw 'Final target appeared before finalizer; refusing overwrite' }
    if ((Get-Sha $stageA) -ne $expectedStageA) { throw 'Protected Stage A changed during raw build' }
    $processes = @(Get-Process -Name SLDWORKS -ErrorAction Stop)
    if ($processes.Count -ne 1 -or $processes[0].Id -ne $expectedProcessId -or -not $processes[0].Responding) {
        throw 'SolidWorks process identity or responsiveness changed before finalizer'
    }

    $finalResult = [B51R1S01MasterSkeletonFinalizer]::Run(
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
    $session['finalizer_result'] = $finalResult
    if ($finalResult -ne 0 -or -not (Test-Path -LiteralPath $target -PathType Leaf)) {
        throw "S01 native finalizer failed with code $finalResult"
    }
    $gate = Get-Content -Raw -Encoding UTF8 -LiteralPath $gateReceipt | ConvertFrom-Json
    if ($gate.status -ne 'S01_PASS_NATIVE_MASTER_SKELETON_CREATED') {
        throw "SR03 S01 gate receipt did not pass: $($gate.status)"
    }
    if ((Get-Sha $stageA) -ne $expectedStageA) { throw 'Protected Stage A changed during S01' }
    if ((Get-Sha $oldHold) -ne $expectedOldHold) { throw 'Immutable old S01 HOLD receipt changed during SR03' }
    if ((Get-Sha $incident) -ne $expectedIncident) { throw 'Immutable automatic-stop incident changed during SR03' }

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
    $session['completed_cad_transaction_at'] = [DateTimeOffset]::Now.ToString('o')
    $exactProcess = Get-Process -Id $expectedProcessId -ErrorAction SilentlyContinue
    if ($null -ne $exactProcess -and $exactProcess.Responding) {
        try { $session['graceful_close_main_window_requested'] = [bool]$exactProcess.CloseMainWindow() } catch { $session['graceful_close_main_window_requested'] = $false }
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
    for ($i = 0; $i -lt 60; $i++) {
        if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -eq 0) { break }
        Start-Sleep -Milliseconds 500
    }
    $remainingProcesses = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
    $normalExit = $remainingProcesses.Count -eq 0
    $session['normal_application_exit'] = $normalExit
    if ($session['status'] -eq 'S01_PASS_NATIVE_MASTER_SKELETON_CREATED' -and -not $normalExit) {
        $session['status'] = 'S01_HOLD_NATIVE_CREATED_APPLICATION_EXIT_PENDING'
        $session['error_message'] = 'Native target and gate receipt exist, but authorized SolidWorks process did not exit normally within 30 seconds'
        $exitCode = 2
    }
    $session['completed_at'] = [DateTimeOffset]::Now.ToString('o')
    $session['protected_stage_a_sha256_after'] = Get-Sha $stageA
    $session['immutable_hold_receipt_sha256_after'] = Get-Sha $oldHold
    $session['automatic_stop_incident_sha256_after'] = Get-Sha $incident
    $session['final_target_exists'] = Test-Path -LiteralPath $target -PathType Leaf
    if (Test-Path -LiteralPath $target -PathType Leaf) {
        $session['final_target_bytes_after_close'] = (Get-Item -LiteralPath $target).Length
        $session['final_target_sha256_after_close'] = Get-Sha $target
    }
    [IO.File]::WriteAllText($sessionReceipt, ($session | ConvertTo-Json -Depth 10) + "`n", $utf8NoBom)

    $ledger = Get-Content -Raw -Encoding UTF8 -LiteralPath $ledgerPath | ConvertFrom-Json
    $event = [pscustomobject]@{
        session_id = $sessionId
        bound_gate = 'S01'
        started_at = $started
        completed_at = $session['completed_at']
        status = $session['status']
        process_id = $expectedProcessId
        new_process_launched = $false
        authorization_sha256 = $expectedAuthorization
        receipt_path = '07_VERIFICATION/AUTONOMOUS/S01/B51R1_SR03_SESSION_EXECUTION_RECEIPT.json'
        gate_receipt_path = '07_VERIFICATION/AUTONOMOUS/S01/B51R1_S01_GATE_RECEIPT_SR03_SUPERSESSION.json'
    }
    $ledger.entries = @($ledger.entries) + @($event)
    $ledger.consumed_since_activation = 4
    $ledger.remaining = 16
    $ledger.authorized_recovery_slot.remaining_attempts = 0
    $ledger.authorized_recovery_slot | Add-Member -NotePropertyName result -NotePropertyValue $session['status'] -Force
    $ledger.last_session_id = $sessionId
    $ledger.last_session_status = $session['status']
    $ledger.updated_at = $session['completed_at']
    if ($session['status'] -eq 'S01_PASS_NATIVE_MASTER_SKELETON_CREATED' -and $normalExit) {
        $ledger.status = 'ACTIVE_G1B_STANDING_SESSION_POOL'
        $ledger.next_session_authorized = $true
        $ledger.next_session_id = 'S02'
    }
    else {
        $ledger.status = 'BLOCKED_SR03_USER_RECOVERY_SLOT_CONSUMED'
        $ledger.next_session_authorized = $false
        $ledger.next_session_id = $null
    }
    [IO.File]::WriteAllText($ledgerPath, ($ledger | ConvertTo-Json -Depth 12) + "`n", $utf8NoBom)
}

$session | ConvertTo-Json -Depth 10
exit $exitCode
