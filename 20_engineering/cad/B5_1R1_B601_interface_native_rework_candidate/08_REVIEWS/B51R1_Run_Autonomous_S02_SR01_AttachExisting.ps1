[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Fa-f0-9]{64}$')]
    [string]$ExpectedAuthorizationSha256,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Fa-f0-9]{64}$')]
    [string]$ExpectedAdmissionSha256,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[A-Fa-f0-9]{64}$')]
    [string]$ExpectedRecoverySupplementSha256
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$s02 = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S02'
$delivery = Join-Path $root '09_DELIVERY\B51R1_AUTONOMOUS_G1A_CLOSURE_20260801'
$target = Join-Path $root '02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2.SLDPRT'
$stageA = Join-Path $root '02_MASTER_SKELETON\B51R1_MASTER_SKELETON_V2_STAGE_A_RECOVERY.SLDPRT'
$s01CurrentGate = Join-Path $root '07_VERIFICATION\AUTONOMOUS\S01\B51R1_S01_CURRENT_GATE.json'
$oldGate = Join-Path $s02 'B51R1_S02_GATE_RECEIPT.json'
$oldSession = Join-Path $s02 'B51R1_S02_SESSION_EXECUTION_RECEIPT.json'
$oldIncident = Join-Path $s02 'B51R1_S02_FAIL_CLOSED_INCIDENT.json'
$authorization = Join-Path $s02 'B51R1_S02_SR01_USER_RECOVERY_REOPEN_AUTHORIZATION.json'
$admission = Join-Path $s02 'B51R1_S02_SR01_ADMISSION_ADDENDUM.json'
$recoverySupplement = Join-Path $delivery 'B51R1_PHASE2A_INPUT_LOCK_V3_S02_SR01_RECOVERY_SUPPLEMENT.json'
$preRecoveryLedgerSnapshot = Join-Path $delivery 'B51R1_AUTONOMOUS_SESSION_POOL_LEDGER_PRE_S02_SR01_SNAPSHOT.json'
$ledgerPath = Join-Path $delivery 'B51R1_AUTONOMOUS_SESSION_POOL_LEDGER.json'
$g1bPath = Join-Path $delivery 'B51R1_G1B_STANDING_SESSION_ADMISSION.json'
$finalLockPath = Join-Path $delivery 'B51R1_PHASE2A_INPUT_LOCK_V3_FINAL.json'
$transitionMapV3 = Join-Path $root '04_CONFIGURATION\B51R1_AUTONOMOUS_GATE_TRANSITION_MAP_V3_SR03.csv'
$s01SupplementR2 = Join-Path $delivery 'B51R1_PHASE2A_INPUT_LOCK_V3_S01_SUPPLEMENT_R2.json'
$verifierSource = Join-Path $PSScriptRoot 'B51R1_S02_MasterSkeletonColdReopenVerifier.cs'
$verifierDll = Join-Path $PSScriptRoot 'B51R1_S02_MasterSkeletonColdReopenVerifier.dll'
$interop = 'F:\Windows_profile\solidworks\SOLIDWORKS\SolidWorks.Interop.sldworks.dll'
$solidworksExe = 'F:\Windows_profile\solidworks\SOLIDWORKS\SLDWORKS.exe'
$gateReceipt = Join-Path $s02 'B51R1_S02_GATE_RECEIPT_SR01_SUPERSESSION.json'
$sessionReceipt = Join-Path $s02 'B51R1_S02_SR01_SESSION_EXECUTION_RECEIPT.json'

$expectedTarget = '71D70F93C356CB4AFDA9C2F594811F683502781C4C6243EF25C2BB888DDEBEFA'
$expectedStageA = '5DEBE5AF52A896CDC3818ADD645725A8E758DB4E5D76F46E3067F9FAA7B5C76B'
$expectedS01CurrentGate = '314A413809DE05EBDF584121D68DA39701683EA9928F0170F90CB0920FF08D95'
$expectedG1b = 'FF33C4FEC8B48C0B759C2BB9E6EA202E89B10DC4789B6385FC15841338276EE6'
$expectedFinalLock = 'AE4FF6021E837651CA019B7ABE8E84B4D0F92183CF158312DF7F826871A3F214'
$expectedTransitionMapV3 = '3B1071670E0EAACF00DF1BC8A3D3F1129CF9A35A09F1DE81FC0C14FA4E502124'
$expectedS01SupplementR2 = 'F6C7D18FA5B063B6F0D1200F13B4EB406AF1486477BC408C06A7EDFE153B3447'
$expectedVerifierSource = 'D00CB87274852E3716D873CC6B20337E63E84453DA2477AD4FA0429A9DB230AF'
$expectedVerifierDll = '7FD5B293E5F7AEBAF3D751334A0A3027AA40E2FB09108BC35A596574D1BE466F'
$expectedOldRunner = '89D4B191ABA5218B60BE822B9FE2F09BF74C2A0656A5E5396F9273EE52478B37'
$expectedSolidworksExe = '4F4B5A8A3706831B65D871BD1549D98CD6F7AA4EEEF17D15873801A7A1668E60'
$expectedOldGate = '5B03B48F4E583CAEFB0EF36E7F1A56AFC85A8E769CCC57CDCB0EFDE65AADD80E'
$expectedOldSession = 'D30BD774F40C5F766C09193015BA46B75A3E8A7B1236359936B8EFB6F6ECEF73'
$expectedOldIncident = 'F203FBA2000A7F0D5CD57B2B5D57F3C9B274BD3735168C741F586DB7AB5494DE'
$expectedPreLedger = '633BCB038236A9D4F83C0F3B0B1ECCB6FFFFB38ED400EE0FAC9183D5BA5476EB'

function Get-Sha([string]$Path) {
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Assert-Hash([string]$Path, [string]$Expected, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label missing: $Path"
    }
    $actual = Get-Sha $Path
    if ($actual -ne $Expected.ToUpperInvariant()) {
        throw "$Label SHA-256 mismatch: $actual"
    }
}

function Write-JsonCreateNew([string]$Path, $Value) {
    if (Test-Path -LiteralPath $Path) {
        throw "Append-only output already exists: $Path"
    }
    $utf8NoBom = New-Object Text.UTF8Encoding($false)
    [IO.File]::WriteAllText(
        $Path,
        ($Value | ConvertTo-Json -Depth 16) + "`n",
        $utf8NoBom)
}

$ExpectedAuthorizationSha256 = $ExpectedAuthorizationSha256.ToUpperInvariant()
$ExpectedAdmissionSha256 = $ExpectedAdmissionSha256.ToUpperInvariant()
$ExpectedRecoverySupplementSha256 = $ExpectedRecoverySupplementSha256.ToUpperInvariant()

Assert-Hash $target $expectedTarget 'Final master skeleton'
Assert-Hash $stageA $expectedStageA 'Protected Stage A'
Assert-Hash $s01CurrentGate $expectedS01CurrentGate 'S01 current gate'
Assert-Hash $g1bPath $expectedG1b 'G1B standing admission'
Assert-Hash $finalLockPath $expectedFinalLock 'Final input lock V3'
Assert-Hash $transitionMapV3 $expectedTransitionMapV3 'Transition map V3'
Assert-Hash $s01SupplementR2 $expectedS01SupplementR2 'S01 supplemental lock R2'
Assert-Hash $verifierSource $expectedVerifierSource 'S02 verifier source'
Assert-Hash $verifierDll $expectedVerifierDll 'S02 verifier DLL'
Assert-Hash (Join-Path $PSScriptRoot 'B51R1_Run_Autonomous_S02.ps1') $expectedOldRunner 'Original S02 runner'
Assert-Hash $solidworksExe $expectedSolidworksExe 'SolidWorks executable'
Assert-Hash $oldGate $expectedOldGate 'Immutable original S02 gate receipt'
Assert-Hash $oldSession $expectedOldSession 'Immutable original S02 session receipt'
Assert-Hash $oldIncident $expectedOldIncident 'Immutable original S02 incident'
Assert-Hash $preRecoveryLedgerSnapshot $expectedPreLedger 'Pre-recovery ledger snapshot'
Assert-Hash $authorization $ExpectedAuthorizationSha256 'S02 recovery authorization'
Assert-Hash $admission $ExpectedAdmissionSha256 'S02 recovery admission'
Assert-Hash $recoverySupplement $ExpectedRecoverySupplementSha256 'S02 recovery supplemental lock'

foreach ($output in @($gateReceipt, $sessionReceipt)) {
    if (Test-Path -LiteralPath $output) {
        throw "S02 recovery output already exists; refusing overwrite: $output"
    }
}

$authorizationData = Get-Content -Raw -Encoding UTF8 -LiteralPath $authorization | ConvertFrom-Json
if ($authorizationData.status -ne 'AUTHORIZED_SINGLE_ADDITIONAL_S02_RECOVERY_SLOT' -or
    $authorizationData.bound_gate -ne 'S02' -or
    $authorizationData.authorized_session_id -ne 'S02_SR01') {
    throw 'S02 recovery authorization contract is invalid'
}
$expectedProcessId = [int]$authorizationData.authorized_existing_process_snapshot.process_id

$admissionData = Get-Content -Raw -Encoding UTF8 -LiteralPath $admission | ConvertFrom-Json
if ($admissionData.status -ne 'S02_SR01_ADMITTED_ONE_TIME_OWNER_EXCEPTION' -or
    $admissionData.authorization.sha256 -ne $ExpectedAuthorizationSha256 -or
    $admissionData.pre_recovery_ledger_snapshot.sha256 -ne $expectedPreLedger -or
    $admissionData.recovery_runner.sha256 -ne (Get-Sha $PSCommandPath)) {
    throw 'S02 recovery admission binding is invalid'
}

$supplement = Get-Content -Raw -Encoding UTF8 -LiteralPath $recoverySupplement | ConvertFrom-Json
if ($supplement.status -ne 'PASS_S02_SR01_RECOVERY_INPUTS_HASH_LOCKED' -or
    $supplement.authorization.sha256 -ne $ExpectedAuthorizationSha256 -or
    $supplement.admission.sha256 -ne $ExpectedAdmissionSha256 -or
    $supplement.parent_s01_supplement_r2.sha256 -ne $expectedS01SupplementR2) {
    throw 'S02 recovery supplemental lock header is invalid'
}
foreach ($tool in @(
    [pscustomobject]@{Id='S02_VERIFIER_SOURCE'; Path=$verifierSource},
    [pscustomobject]@{Id='S02_VERIFIER_DLL'; Path=$verifierDll},
    [pscustomobject]@{Id='S02_ORIGINAL_RUNNER'; Path=(Join-Path $PSScriptRoot 'B51R1_Run_Autonomous_S02.ps1')},
    [pscustomobject]@{Id='S02_SR01_ATTACH_EXISTING_RUNNER'; Path=$PSCommandPath}
)) {
    $locked = @($supplement.locked_items | Where-Object { $_.id -eq $tool.Id })
    if ($locked.Count -ne 1 -or $locked[0].sha256 -ne (Get-Sha $tool.Path)) {
        throw "Recovery supplemental tool lock mismatch: $($tool.Id)"
    }
}

$ledger = Get-Content -Raw -Encoding UTF8 -LiteralPath $ledgerPath | ConvertFrom-Json
if ($ledger.status -ne 'ACTIVE_USER_REOPENED_SINGLE_S02_RECOVERY_SLOT' -or
    [int]$ledger.budget -ne 20 -or
    [int]$ledger.consumed_since_activation -ne 5 -or
    [int]$ledger.remaining -ne 15 -or
    -not [bool]$ledger.next_session_authorized -or
    [string]$ledger.next_session_id -ne 'S02_SR01') {
    throw 'Live ledger is not in the exact S02_SR01 authorization state'
}
if (@($ledger.entries | Where-Object { $_.session_id -eq 'S02_SR01' }).Count -ne 0) {
    throw 'S02_SR01 already exists in the live ledger'
}
if ($ledger.s02_user_recovery_reopen_authorization.sha256 -ne $ExpectedAuthorizationSha256 -or
    $ledger.s02_recovery_admission.sha256 -ne $ExpectedAdmissionSha256 -or
    $ledger.s02_recovery_supplement.sha256 -ne $ExpectedRecoverySupplementSha256 -or
    $ledger.s02_authorized_recovery_slot.session_id -ne 'S02_SR01' -or
    [int]$ledger.s02_authorized_recovery_slot.remaining_attempts -ne 1) {
    throw 'Live ledger S02 recovery authorization binding is invalid'
}

$processes = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue)
if ($processes.Count -ne 1) {
    throw "Expected exactly one existing SLDWORKS process; found $($processes.Count)"
}
$authorizedProcess = $processes[0]
$authorizedProcess.Refresh()
if ($authorizedProcess.Id -ne $expectedProcessId -or
    -not $authorizedProcess.Responding -or
    $authorizedProcess.MainWindowHandle -eq 0) {
    throw 'The sole existing SolidWorks process does not match the authorized visible responsive PID'
}
if ((Get-Sha $authorizedProcess.Path) -ne $expectedSolidworksExe) {
    throw 'The authorized SolidWorks executable hash differs from the locked executable'
}
if ($authorizedProcess.StartTime.ToString('o') -ne
    [string]$authorizationData.authorized_existing_process_snapshot.start_time) {
    throw 'The authorized SolidWorks process start time changed'
}

$started = [DateTimeOffset]::Now.ToString('o')
$session = [ordered]@{
    schema = 'B51R1_S02_SR01_SESSION_EXECUTION_RECEIPT_V1'
    session_id = 'S02_SR01'
    bound_gate = 'S02'
    started_at = $started
    status = 'S02_SR01_FAIL_CLOSED_NOT_STARTED'
    process_id = $expectedProcessId
    process_start_time = $authorizedProcess.StartTime.ToString('o')
    launch_mode = 'ATTACH_EXISTING_USER_OPENED_VISIBLE_RESPONSIVE_PROCESS'
    new_process_launched = $false
    authorization_sha256 = $ExpectedAuthorizationSha256
    admission_sha256 = $ExpectedAdmissionSha256
    recovery_supplement_sha256 = $ExpectedRecoverySupplementSha256
    target_sha256_before = $expectedTarget
    protected_stage_a_sha256_before = $expectedStageA
    s01_current_gate_sha256_before = $expectedS01CurrentGate
    original_s02_gate_sha256 = $expectedOldGate
    original_s02_session_sha256 = $expectedOldSession
    original_s02_incident_sha256 = $expectedOldIncident
    open_mode = 'READ_ONLY'
    save_permitted = $false
}
$attemptConsumed = $false
$exitCode = 1
try {
    [void][Reflection.Assembly]::LoadFrom($interop)
    [void][Reflection.Assembly]::LoadFrom($verifierDll)

    $processesAtAttach = @(Get-Process -Name SLDWORKS -ErrorAction Stop)
    if ($processesAtAttach.Count -ne 1 -or
        $processesAtAttach[0].Id -ne $expectedProcessId -or
        -not $processesAtAttach[0].Responding -or
        $processesAtAttach[0].MainWindowHandle -eq 0) {
        throw 'Exact single-process guard failed immediately before COM attach'
    }

    $attemptConsumed = $true
    $session['attempt_consumed_at'] = [DateTimeOffset]::Now.ToString('o')
    $result = [B51R1S02MasterSkeletonColdReopenVerifier]::Run(
        $target,
        $stageA,
        $gateReceipt,
        $expectedProcessId,
        $s01CurrentGate,
        $expectedS01CurrentGate,
        $expectedTarget,
        $expectedStageA,
        $expectedG1b,
        $expectedFinalLock
    )
    $session['verifier_result'] = $result
    if ($result -ne 0) {
        throw "S02_SR01 cold-reopen verifier failed with code $result"
    }
    $gate = Get-Content -Raw -Encoding UTF8 -LiteralPath $gateReceipt | ConvertFrom-Json
    if ($gate.status -ne 'S02_PASS_MASTER_SKELETON_COLD_REOPEN') {
        throw "S02_SR01 gate receipt did not pass: $($gate.status)"
    }
    if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
        throw 'SolidWorks remains after verifier-requested normal ExitApp'
    }
    Assert-Hash $target $expectedTarget 'Final master skeleton after S02_SR01'
    Assert-Hash $stageA $expectedStageA 'Protected Stage A after S02_SR01'
    Assert-Hash $s01CurrentGate $expectedS01CurrentGate 'S01 current gate after S02_SR01'
    Assert-Hash $oldGate $expectedOldGate 'Original S02 gate after S02_SR01'
    Assert-Hash $oldSession $expectedOldSession 'Original S02 session after S02_SR01'
    Assert-Hash $oldIncident $expectedOldIncident 'Original S02 incident after S02_SR01'

    $session['status'] = 'S02_PASS_MASTER_SKELETON_COLD_REOPEN'
    $session['gate_receipt_sha256'] = Get-Sha $gateReceipt
    $session['target_sha256_after'] = Get-Sha $target
    $session['protected_stage_a_sha256_after'] = Get-Sha $stageA
    $session['s01_current_gate_sha256_after'] = Get-Sha $s01CurrentGate
    $session['normal_application_exit'] = $true
    $exitCode = 0
}
catch {
    $session['status'] = 'S02_SR01_FAIL_CLOSED'
    $session['error_type'] = $_.Exception.GetType().FullName
    $session['error_message'] = $_.Exception.Message
    $session['normal_application_exit'] =
        (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -eq 0)
    $exitCode = 1
}
finally {
    # Never terminate or kill SolidWorks. After a consumed attempt, request only
    # a graceful close if the verifier did not already call ExitApp.
    if ($attemptConsumed -and
        @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -ne 0) {
        $remaining = Get-Process -Id $expectedProcessId -ErrorAction SilentlyContinue
        if ($null -ne $remaining -and $remaining.Responding) {
            try {
                $session['graceful_close_main_window_requested'] =
                    [bool]$remaining.CloseMainWindow()
            }
            catch {
                $session['graceful_close_main_window_requested'] = $false
            }
        }
        for ($attempt = 0; $attempt -lt 60; $attempt++) {
            if (@(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count -eq 0) {
                break
            }
            Start-Sleep -Milliseconds 500
        }
    }

    $session['attempt_consumed'] = $attemptConsumed
    $session['completed_at'] = [DateTimeOffset]::Now.ToString('o')
    $processCountAfter = @(Get-Process -Name SLDWORKS -ErrorAction SilentlyContinue).Count
    $session['solidworks_process_count_after'] = $processCountAfter
    if ($session['status'] -eq 'S02_PASS_MASTER_SKELETON_COLD_REOPEN' -and
        $processCountAfter -ne 0) {
        $session['status'] = 'S02_SR01_HOLD_PROCESS_EXIT_PENDING'
        $session['normal_application_exit'] = $false
        $session['error_message'] = 'Verification passed but SolidWorks did not exit normally'
        $exitCode = 2
    }
    $session['target_sha256_final'] = Get-Sha $target
    $session['protected_stage_a_sha256_final'] = Get-Sha $stageA
    $session['s01_current_gate_sha256_final'] = Get-Sha $s01CurrentGate
    $session['original_s02_gate_sha256_final'] = Get-Sha $oldGate
    $session['original_s02_session_sha256_final'] = Get-Sha $oldSession
    $session['original_s02_incident_sha256_final'] = Get-Sha $oldIncident
    Write-JsonCreateNew $sessionReceipt $session

    if ($attemptConsumed) {
        $liveLedger = Get-Content -Raw -Encoding UTF8 -LiteralPath $ledgerPath | ConvertFrom-Json
        if ($liveLedger.status -ne 'ACTIVE_USER_REOPENED_SINGLE_S02_RECOVERY_SLOT' -or
            [int]$liveLedger.consumed_since_activation -ne 5 -or
            [int]$liveLedger.remaining -ne 15 -or
            @($liveLedger.entries | Where-Object { $_.session_id -eq 'S02_SR01' }).Count -ne 0) {
            throw 'Live ledger changed unexpectedly during S02_SR01'
        }
        $event = [pscustomobject]@{
            session_id = 'S02_SR01'
            bound_gate = 'S02'
            started_at = $started
            completed_at = $session['completed_at']
            status = $session['status']
            process_id = $expectedProcessId
            new_process_launched = $false
            authorization_sha256 = $ExpectedAuthorizationSha256
            admission_sha256 = $ExpectedAdmissionSha256
            recovery_supplement_sha256 = $ExpectedRecoverySupplementSha256
            receipt_path = '07_VERIFICATION/AUTONOMOUS/S02/B51R1_S02_SR01_SESSION_EXECUTION_RECEIPT.json'
            gate_receipt_path = '07_VERIFICATION/AUTONOMOUS/S02/B51R1_S02_GATE_RECEIPT_SR01_SUPERSESSION.json'
        }
        $liveLedger.entries = @($liveLedger.entries) + @($event)
        $liveLedger.consumed_since_activation = 6
        $liveLedger.remaining = 14
        $liveLedger.last_session_id = 'S02_SR01'
        $liveLedger.last_session_status = $session['status']
        $liveLedger.updated_at = $session['completed_at']
        $liveLedger.s02_authorized_recovery_slot.remaining_attempts = 0
        $liveLedger.s02_authorized_recovery_slot.result = $session['status']
        if ($session['status'] -eq 'S02_PASS_MASTER_SKELETON_COLD_REOPEN' -and
            $processCountAfter -eq 0) {
            $liveLedger.status = 'S02_RECOVERY_PASS_PENDING_APPEND_ONLY_SUPERSESSION'
        }
        else {
            $liveLedger.status = 'BLOCKED_S02_SR01_FAIL_CLOSED'
        }
        $liveLedger.next_session_authorized = $false
        $liveLedger.next_session_id = $null
        $utf8NoBom = New-Object Text.UTF8Encoding($false)
        [IO.File]::WriteAllText(
            $ledgerPath,
            ($liveLedger | ConvertTo-Json -Depth 16) + "`n",
            $utf8NoBom)
    }
}

$session | ConvertTo-Json -Depth 16
exit $exitCode
